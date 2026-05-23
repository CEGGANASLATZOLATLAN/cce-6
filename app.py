from flask import (Flask, render_template, redirect, url_for, request,
                   session, flash, jsonify, make_response, Response)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date, datetime, timedelta
from functools import wraps
import os, random, json, urllib.parse, requests as req_lib

# .env dosyasını oku
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── App & Config ───────────────────────────────────────────────────────────────
_DB_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'words.db')

app = Flask(__name__)
app.config.update(
    SECRET_KEY='kelime-ezberleme-2024-gizli',
    SQLALCHEMY_DATABASE_URI=_DB_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=os.path.join('static', 'uploads', 'words'),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)
db = SQLAlchemy(app)

# Tüm HTML sayfaları cache'lenmesini engelle
@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response

ALLOWED_EXT    = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
STAGE_DAYS     = {1: 1, 2: 7, 3: 30, 4: 90, 5: 180, 6: 365}
STAGE_LABELS   = {
    0: 'Yeni',    1: '1. Gün',  2: '1. Hafta',
    3: '1. Ay',   4: '3. Ay',  5: '6. Ay',
    6: '1. Yıl',  7: 'Öğrenildi',
}

# ── Models ─────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.Unicode(255), unique=True, nullable=False)
    password      = db.Column(db.Unicode(255), nullable=False)
    email         = db.Column(db.Unicode(255), default='')
    words_per_day = db.Column(db.Integer, default=10)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class Word(db.Model):
    __tablename__ = 'words'
    id       = db.Column(db.Integer, primary_key=True)
    eng_word = db.Column(db.Unicode(255), nullable=False)
    tur_word = db.Column(db.Unicode(255), nullable=False)
    picture  = db.Column(db.Unicode(500), default='')
    audio    = db.Column(db.Unicode(500), default='')
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    samples  = db.relationship('WordSample', backref='word', lazy=True,
                               cascade='all, delete-orphan')

class WordSample(db.Model):
    __tablename__ = 'word_samples'
    id      = db.Column(db.Integer, primary_key=True)
    word_id = db.Column(db.Integer, db.ForeignKey('words.id'), nullable=False)
    sample  = db.Column(db.UnicodeText, nullable=False)

class UserWordProgress(db.Model):
    __tablename__      = 'user_word_progress'
    id                 = db.Column(db.Integer, primary_key=True)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_id            = db.Column(db.Integer, db.ForeignKey('words.id'), nullable=False)
    stage              = db.Column(db.Integer, default=0)
    first_correct_date = db.Column(db.Date, nullable=True)
    next_review        = db.Column(db.Date, nullable=True)
    last_reviewed      = db.Column(db.Date, nullable=True)
    is_learned         = db.Column(db.Boolean, default=False)
    introduced_date    = db.Column(db.Date, default=date.today)
    word               = db.relationship('Word', lazy=True)

class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    word_id      = db.Column(db.Integer, db.ForeignKey('words.id'), nullable=False)
    is_correct   = db.Column(db.Boolean, nullable=False)
    answered_at  = db.Column(db.DateTime, default=datetime.utcnow)
    quiz_date    = db.Column(db.Date, default=date.today)
    stage_before = db.Column(db.Integer, default=0)
    word         = db.relationship('Word', lazy=True)

# ── Helpers ─────────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Lütfen giriş yapın.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_today_quiz_words(user_id):
    today = date.today()
    user  = User.query.get(user_id)

    # 1. Spaced-review words due today
    review_ids = [
        p.word_id for p in UserWordProgress.query.filter(
            UserWordProgress.user_id    == user_id,
            UserWordProgress.is_learned == False,
            UserWordProgress.stage      >  0,
            UserWordProgress.next_review <= today,
        ).all()
    ]

    # 2. Failed words (stage=0, need re-introduction)
    failed_ids = [
        p.word_id for p in UserWordProgress.query.filter(
            UserWordProgress.user_id    == user_id,
            UserWordProgress.is_learned == False,
            UserWordProgress.stage      == 0,
            UserWordProgress.next_review.is_(None),
        ).all()
        if p.last_reviewed is None or p.last_reviewed < today
    ]

    # 3. Brand-new words (fill up to daily limit)
    known_ids     = {p.word_id for p in
                     UserWordProgress.query.filter_by(user_id=user_id).all()}
    new_pool      = [w.id for w in Word.query.all() if w.id not in known_ids]
    new_limit     = max(0, user.words_per_day - len(review_ids) - len(failed_ids))
    new_ids       = random.sample(new_pool, min(new_limit, len(new_pool)))

    combined = list(dict.fromkeys(review_ids + failed_ids + new_ids))
    random.shuffle(combined)
    return combined

def update_word_progress(user_id, word_id, is_correct):
    today    = date.today()
    progress = UserWordProgress.query.filter_by(
        user_id=user_id, word_id=word_id
    ).first()

    if not progress:
        progress = UserWordProgress(
            user_id=user_id, word_id=word_id,
            stage=0, introduced_date=today,
        )
        db.session.add(progress)

    stage_before        = progress.stage
    progress.last_reviewed = today

    if is_correct:
        if progress.stage == 0:
            progress.first_correct_date = today
        progress.stage += 1

        if progress.stage >= 7:
            progress.is_learned  = True
            progress.next_review = None
        else:
            days = STAGE_DAYS[progress.stage]
            progress.next_review = (
                progress.first_correct_date + timedelta(days=days)
            )
    else:
        progress.stage              = 0
        progress.first_correct_date = None
        progress.next_review        = None

    db.session.add(QuizAnswer(
        user_id=user_id, word_id=word_id,
        is_correct=is_correct, quiz_date=today,
        stage_before=stage_before,
    ))
    db.session.commit()
    return progress

def get_distractors(correct_word_id, n=3):
    others = Word.query.filter(Word.id != correct_word_id).all()
    return [w.tur_word for w in random.sample(others, min(n, len(others)))]

def get_user_stats(user_id):
    total    = Word.query.count()
    learned  = UserWordProgress.query.filter_by(
        user_id=user_id, is_learned=True).count()
    in_prog  = UserWordProgress.query.filter(
        UserWordProgress.user_id    == user_id,
        UserWordProgress.is_learned == False,
        UserWordProgress.stage      >  0,
    ).count()
    today_a  = QuizAnswer.query.filter_by(
        user_id=user_id, quiz_date=date.today()).all()
    correct  = sum(1 for a in today_a if a.is_correct)
    return dict(
        total_words=total, learned=learned, in_progress=in_prog,
        correct_today=correct, total_today=len(today_a),
    )

# ── Auth ────────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        email    = request.form.get('email', '').strip()

        if not username or not password:
            flash('Kullanıcı adı ve şifre zorunludur.', 'danger')
        elif password != confirm:
            flash('Şifreler eşleşmiyor.', 'danger')
        elif len(password) < 4:
            flash('Şifre en az 4 karakter olmalı.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'danger')
        else:
            user = User(
                username=username,
                password=generate_password_hash(password),
                email=email,
            )
            db.session.add(user)
            db.session.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user     = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id']  = user.id
            session['username'] = user.username
            flash(f'Hoş geldin, {user.username}!', 'success')
            return redirect(url_for('index'))
        flash('Kullanıcı adı veya şifre hatalı.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        new_pass = request.form.get('new_password', '')
        confirm  = request.form.get('confirm_password', '')
        user     = User.query.filter_by(username=username).first()
        if not user:
            flash('Bu kullanıcı adı bulunamadı.', 'danger')
        elif new_pass != confirm:
            flash('Şifreler eşleşmiyor.', 'danger')
        elif len(new_pass) < 4:
            flash('Şifre en az 4 karakter olmalı.', 'danger')
        else:
            user.password = generate_password_hash(new_pass)
            db.session.commit()
            flash('Şifre başarıyla güncellendi!', 'success')
            return redirect(url_for('login'))
    return render_template('forgot_password.html')

# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    # Giriş yapılmamışsa landing page göster
    if 'user_id' not in session:
        return render_template('landing.html')
    stats              = get_user_stats(session['user_id'])
    today_words        = get_today_quiz_words(session['user_id'])
    stats['quiz_count']     = len(today_words)
    stats['quiz_available'] = len(today_words) > 0
    return render_template('index.html', stats=stats)

# ── Words ──────────────────────────────────────────────────────────────────────

@app.route('/words')
@login_required
def words_list():
    words = Word.query.order_by(Word.eng_word).all()
    user_id = session['user_id']
    progress_map = {
        p.word_id: p
        for p in UserWordProgress.query.filter_by(user_id=user_id).all()
    }
    return render_template('words_list.html', words=words, progress_map=progress_map,
                           STAGE_LABELS=STAGE_LABELS)

@app.route('/words/add', methods=['GET', 'POST'])
@login_required
def word_add():
    if request.method == 'POST':
        eng = request.form.get('eng_word', '').strip().lower()
        tur = request.form.get('tur_word', '').strip()
        if not eng or not tur:
            flash('İngilizce ve Türkçe kelime zorunludur.', 'danger')
            return render_template('word_add.html')

        word = Word(eng_word=eng, tur_word=tur, added_by=session['user_id'])
        pic  = request.files.get('picture')
        if pic and pic.filename and allowed_file(pic.filename):
            ext      = pic.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f"{eng}_{random.randint(1000,9999)}.{ext}")
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            word.picture = filename

        db.session.add(word)
        db.session.flush()

        for s in request.form.getlist('samples'):
            s = s.strip()
            if s:
                db.session.add(WordSample(word_id=word.id, sample=s))

        db.session.commit()
        flash(f'"{eng}" kelimesi eklendi!', 'success')
        return redirect(url_for('words_list'))

    return render_template('word_add.html')

@app.route('/words/edit/<int:word_id>', methods=['GET', 'POST'])
@login_required
def word_edit(word_id):
    word = Word.query.get_or_404(word_id)
    if request.method == 'POST':
        word.eng_word = request.form.get('eng_word', '').strip().lower()
        word.tur_word = request.form.get('tur_word', '').strip()

        pic = request.files.get('picture')
        if pic and pic.filename and allowed_file(pic.filename):
            ext      = pic.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f"{word.eng_word}_{random.randint(1000,9999)}.{ext}")
            pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            word.picture = filename

        for s in list(word.samples):
            db.session.delete(s)
        for s in request.form.getlist('samples'):
            s = s.strip()
            if s:
                db.session.add(WordSample(word_id=word.id, sample=s))

        db.session.commit()
        flash('Kelime güncellendi!', 'success')
        return redirect(url_for('words_list'))

    return render_template('word_edit.html', word=word)

@app.route('/words/delete/<int:word_id>', methods=['POST'])
@login_required
def word_delete(word_id):
    word = Word.query.get_or_404(word_id)
    UserWordProgress.query.filter_by(word_id=word_id).delete()
    QuizAnswer.query.filter_by(word_id=word_id).delete()
    db.session.delete(word)
    db.session.commit()
    flash('Kelime silindi.', 'info')
    return redirect(url_for('words_list'))

# ── Quiz ───────────────────────────────────────────────────────────────────────

@app.route('/quiz')
@login_required
def quiz_start():
    word_ids = get_today_quiz_words(session['user_id'])
    if not word_ids:
        flash('Bugün için sınav kelimesi yok. Yarın tekrar gel!', 'info')
        return redirect(url_for('index'))
    session['quiz_words']   = word_ids
    session['quiz_index']   = 0
    session['quiz_results'] = {}
    return redirect(url_for('quiz_question'))

@app.route('/quiz/question')
@login_required
def quiz_question():
    word_ids = session.get('quiz_words', [])
    index    = session.get('quiz_index', 0)

    if index >= len(word_ids):
        return redirect(url_for('quiz_result'))

    word_id  = word_ids[index]
    word     = Word.query.get(word_id)
    if not word:
        session['quiz_index'] = index + 1
        session.modified = True
        return redirect(url_for('quiz_question'))

    progress = UserWordProgress.query.filter_by(
        user_id=session['user_id'], word_id=word_id).first()
    stage    = progress.stage if progress else 0

    distractors = get_distractors(word_id, 3)
    options     = distractors + [word.tur_word]
    random.shuffle(options)

    return render_template('quiz.html',
        word=word,
        options=options,
        stage=stage,
        stage_label=STAGE_LABELS.get(stage, ''),
        question_num=index + 1,
        total=len(word_ids),
        progress_pct=int((index / len(word_ids)) * 100),
    )

@app.route('/quiz/answer', methods=['POST'])
@login_required
def quiz_answer():
    word_ids = session.get('quiz_words', [])
    index    = session.get('quiz_index', 0)
    if index >= len(word_ids):
        return redirect(url_for('quiz_result'))

    word_id = word_ids[index]
    word    = Word.query.get(word_id)
    chosen  = request.form.get('answer', '').strip().lower()
    correct = (chosen == word.tur_word.strip().lower())

    update_word_progress(session['user_id'], word_id, correct)

    results = session.get('quiz_results', {})
    results[str(word_id)] = {
        'correct': correct,
        'chosen':  chosen,
        'answer':  word.tur_word,
        'eng':     word.eng_word,
        'picture': word.picture,
    }
    session['quiz_results'] = results
    session['quiz_index']   = index + 1
    session.modified = True

    return jsonify({'ok': True})

@app.route('/quiz/result')
@login_required
def quiz_result():
    results = session.get('quiz_results', {})
    correct = sum(1 for r in results.values() if r['correct'])
    total   = len(results)
    pct     = int((correct / total) * 100) if total else 0
    return render_template('quiz_result.html',
        results=results, correct=correct, total=total, pct=pct)

# ── Settings ───────────────────────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        try:
            n = max(1, min(100, int(request.form.get('words_per_day', 10))))
        except ValueError:
            n = 10
        user.words_per_day = n
        db.session.commit()
        flash('Ayarlar kaydedildi!', 'success')
    return render_template('settings.html', user=user)

# ── Report ─────────────────────────────────────────────────────────────────────

@app.route('/report')
@login_required
def report():
    uid = session['user_id']

    total_a   = QuizAnswer.query.filter_by(user_id=uid).count()
    correct_a = QuizAnswer.query.filter_by(user_id=uid, is_correct=True).count()
    overall   = int((correct_a / total_a) * 100) if total_a else 0

    learned = UserWordProgress.query.filter_by(
        user_id=uid, is_learned=True).count()

    stage_data = {}
    for s in range(8):
        stage_data[s] = UserWordProgress.query.filter_by(
            user_id=uid, stage=s, is_learned=False).count()
    stage_data[7] = learned

    recent = (QuizAnswer.query
              .filter_by(user_id=uid)
              .order_by(QuizAnswer.answered_at.desc())
              .limit(20).all())

    word_stats = []
    for p in UserWordProgress.query.filter_by(user_id=uid).all():
        word = Word.query.get(p.word_id)
        if not word:
            continue
        ans = QuizAnswer.query.filter_by(user_id=uid, word_id=p.word_id).all()
        c   = sum(1 for a in ans if a.is_correct)
        t   = len(ans)
        word_stats.append({
            'word': word, 'stage': p.stage, 'learned': p.is_learned,
            'correct': c, 'total': t,
            'pct': int((c / t) * 100) if t else 0,
        })
    word_stats.sort(key=lambda x: x['pct'])

    return render_template('report.html',
        total_answers=total_a, correct_all=correct_a, overall_pct=overall,
        learned_count=learned, stage_data=stage_data, recent=recent,
        word_stats=word_stats, STAGE_LABELS=STAGE_LABELS,
        now=datetime.utcnow(),
    )

# ── Wordle ─────────────────────────────────────────────────────────────────────

@app.route('/wordle')
@login_required
def wordle():
    uid = session['user_id']
    learned_ids = [p.word_id for p in
                   UserWordProgress.query.filter_by(user_id=uid, is_learned=True).all()]

    if learned_ids:
        pool = Word.query.filter(Word.id.in_(learned_ids)).all()
    else:
        pool = []

    if not pool:
        pool = Word.query.all()

    if not pool:
        flash('Wordle için kelime bulunamadı. Kelime ekleyin!', 'warning')
        return redirect(url_for('index'))

    # Önceki kelimeyi tekrar seçme
    last = session.get('last_wordle_word', '')
    eligible = [w for w in pool if w.eng_word != last]
    if not eligible:
        eligible = pool
    target = random.choice(eligible)
    session['last_wordle_word'] = target.eng_word

    return render_template('wordle.html',
        target_word=target.eng_word.upper(),
        target_tur=target.tur_word,
        word_length=len(target.eng_word),
    )

# ── Word Chain ─────────────────────────────────────────────────────────────────

_image_cache = {}

@app.route('/api/generate-image')
@login_required
def generate_image_proxy():
    import time, hashlib
    prompt = request.args.get('prompt', 'fantasy scene')
    seed   = request.args.get('seed', '1')

    cache_key = hashlib.md5((prompt + seed).encode()).hexdigest()
    now = time.time()
    if cache_key in _image_cache:
        ts, content, mime = _image_cache[cache_key]
        if now - ts < 600:
            return Response(content, mimetype=mime)

    hf_token = os.environ.get('HF_TOKEN', '')
    hf_models = [
        'black-forest-labs/FLUX.1-schnell',
        'black-forest-labs/FLUX.1-dev',
    ]
    hdrs = {
        'Authorization': f'Bearer {hf_token}',
        'Content-Type': 'application/json',
    }
    payload = json.dumps({'inputs': prompt})

    for model in hf_models:
        url = f'https://router.huggingface.co/hf-inference/models/{model}'
        try:
            r = req_lib.post(url, headers=hdrs, data=payload, timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                mime = r.headers.get('content-type', 'image/jpeg')
                _image_cache[cache_key] = (now, r.content, mime)
                return Response(r.content, mimetype=mime)
            elif r.status_code == 503:
                time.sleep(8)
                r2 = req_lib.post(url, headers=hdrs, data=payload, timeout=60)
                if r2.status_code == 200 and len(r2.content) > 1000:
                    mime = r2.headers.get('content-type', 'image/jpeg')
                    _image_cache[cache_key] = (now, r2.content, mime)
                    return Response(r2.content, mimetype=mime)
        except Exception:
            pass

    return ('Görsel oluşturulamadı', 500)

@app.route('/word-chain', methods=['GET', 'POST'])
@login_required
def word_chain():
    all_words     = Word.query.order_by(Word.eng_word).all()
    story         = None
    selected_words = []

    if request.method == 'POST':
        ids = request.form.getlist('word_ids')
        if len(ids) < 3:
            flash('En az 3 kelime seçmelisiniz.', 'warning')
        else:
            selected_words = Word.query.filter(Word.id.in_(ids)).all()
            story = _generate_story(selected_words)

    return render_template('word_chain.html',
        all_words=all_words, story=story, selected_words=selected_words)

def _generate_story(words):
    word_list    = [w.eng_word for w in words]
    translations = {w.eng_word: w.tur_word for w in words}

    # Try Claude API if key exists
    try:
        import anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            wstr   = ', '.join(word_list)
            msg    = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=900,
                messages=[{'role': 'user', 'content': (
                    f"İki şey yap ve SADECE geçerli JSON döndür, başka hiçbir şey yazma.\n\n"
                    f"1. Şu İngilizce kelimelerin TÜMÜNÜ kullanan akıcı, etkileyici bir hikaye yaz TÜRKÇE olarak: {wstr}.\n"
                    f"   Kurallar:\n"
                    f"   - Her İngilizce kelime hikayede BÜYÜK HARFLE (ALL CAPS) tam olarak BİR KEZ geçmeli.\n"
                    f"   - Kelimeleri doğal kullan: isim, fiil, sıfat olarak; hepsini özel isim yapma.\n"
                    f"   - Cümle yapılarını çeşitlendir: kısa vurucu, uzun betimleyici, diyalog, soru.\n"
                    f"   - Uzunluk: {len(word_list) + 2} ile {len(word_list) + 4} cümle.\n\n"
                    f"2. Bu hikayenin atmosferini yansıtan, görsel ve sinematik bir Stable Diffusion görsel promptu yaz "
                    f"(İNGİLİZCE, max 40 kelime, virgülle ayrılmış görsel tanımlayıcılar).\n\n"
                    f"JSON formatı: {{\"story\": \"...\", \"image_prompt\": \"...\"}}"
                )}],
            )
            raw = msg.content[0].text.strip()
            # JSON parse et
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            parsed = json.loads(m.group()) if m else {}
            story_text   = parsed.get('story', raw)
            image_prompt = parsed.get('image_prompt', wstr + ', cinematic scene, fantasy art')
            image_prompt = ' '.join(image_prompt.split())  # satır sonlarını ve fazla boşlukları temizle
            return {
                'text': story_text,
                'words': word_list,
                'translations': translations,
                'ai': True,
                'image_prompt': image_prompt,
            }
    except Exception:
        pass

    # Fallback: varied sentence templates — each word gets a different sentence structure
    return {'text': _varied_template(word_list), 'words': word_list,
            'translations': translations, 'ai': False,
            'image_prompt': ', '.join(word_list) + ', cinematic story scene, detailed illustration, fantasy art style'}


_STORY_STYLES = [
    {
        'name': 'gizem',
        'intro': [
            "O gece hiçbir şey normal değildi.",
            "Yıllar sonra bile o anı hatırladığında içi ürperiyordu.",
            "Kapı yavaşça açıldığında içeride kimse yoktu — ya da öyle sanıyordu.",
        ],
        'patterns': [
            lambda w: f"**{w.upper()}** tam da aradığı şeydi, ama onu bulmak her şeyi daha da gizemli hale getirdi.",
            lambda w: f'"Bu **{w.upper()}** nedir?" diye sordu; hiç kimse cevap veremedi.',
            lambda w: f"**{w.upper()}**'ın izi soğuk karanlıkta kaybolup gidiyordu.",
            lambda w: f"**{w.upper()}**'ı görünce derin bir nefes aldı — bu bir tesadüf olamazdı.",
            lambda w: f"Yıllardır saklanan sır sonunda **{w.upper()}**'la gün yüzüne çıktı.",
            lambda w: f"**{w.upper()}** hakkında hiçbir şey söylenmemişti; bu da en büyük ipucuydu.",
            lambda w: f"Eski haritada yalnızca iki kelime yazıyordu: **{w.upper()}**.",
        ],
        'outro': [
            "Sabah olduğunda her şey değişmişti — ama kimse nedenini bilmiyordu.",
            "O günden sonra o yere bir daha dönmedi.",
            "Cevap oradaydı; yeter ki doğru soruyu sormayı bilmek gerekiyordu.",
        ],
    },
    {
        'name': 'macera',
        'intro': [
            "Yolculuk tam da planladığı gibi başlamadı.",
            "Harita elindeydi ama gidecek yer belirsizdi.",
            "Hiç bu kadar uzağa gitmemişti — ve bunu sevdi.",
        ],
        'patterns': [
            lambda w: f"Dağın zirvesinde **{w.upper()}** onu bekliyordu; yorgunluğu bir anda uçtu.",
            lambda w: f"**{w.upper()}** olmadan bu yolu tamamlamak imkânsızdı.",
            lambda w: f"Çantasından çıkardığı **{w.upper()}** tüm dengeleri değiştirdi.",
            lambda w: f'"Eğer **{w.upper()}** bulursak," dedi rehberi, "geri dönebiliriz."',
            lambda w: f"Orman **{w.upper()}**'la doluydu; tehlikeli ama büyüleyici.",
            lambda w: f"**{w.upper()}**'ı geçmeden bir sonraki adımı atamadı.",
            lambda w: f"Son köyde yaşlı bir adam **{w.upper()}**'ın sırrını fısıldadı.",
        ],
        'outro': [
            "Yolculuk bitmişti — ama asıl macera şimdi başlıyordu.",
            "Geri döndüğünde artık aynı kişi değildi.",
            "Bazı yollar vardır; seni götürdükleri yerden çok, değiştirdikleri şeyle kalır içinde.",
        ],
    },
    {
        'name': 'dram',
        'intro': [
            "Bazı şeyler söylenmeden de anlaşılır.",
            "O sabah güneş farklı doğmuştu — sanki bir şeyler biliyordu.",
            "İki kişi aynı odada oturuyordu ama aralarındaki mesafe kilometreler uzunluğundaydı.",
        ],
        'patterns': [
            lambda w: f"**{w.upper()}** hep ikisi arasında durmuştu; kimse bunu dile getirmemişti.",
            lambda w: f'"**{w.upper()}**..." dedi; kelimeler bitmişti, sadece bu kaldı.',
            lambda w: f"**{w.upper()}**'ı ilk duyduğunda gözleri dolmuştu — neden olduğunu bilmiyordu.",
            lambda w: f"**{w.upper()}** olmadan geçen her gün bir eksiklik gibi hissettiriyordu.",
            lambda w: f"Ona verdiği son şey **{w.upper()}**'dı; belki de en değerlisiydi.",
            lambda w: f"**{w.upper()}** zamanla anlam kazandı — acı ama gerçek.",
            lambda w: f"Sessizliğin içinde **{w.upper()}** vardı; onu fark etmek için yıllar geçmesi gerekmişti.",
        ],
        'outro': [
            "Bazı şeyler biter; izleri hiç silinmez.",
            "Belki de en doğrusu buydu — söylenmemiş, ama hissedilmiş.",
            "Zaman her şeyi değiştirir; sadece en derindeki şeylere dokunamaz.",
        ],
    },
    {
        'name': 'bilim-kurgu',
        'intro': [
            "2157'de dünya artık tanıdık değildi.",
            "Sistem uyarı verdiğinde çok geçti.",
            "İlk sinyal geldiğinde kimse ciddiye almadı.",
        ],
        'patterns': [
            lambda w: f"**{w.upper()}** protokolü devreye girdiğinde tüm ekranlar karardı.",
            lambda w: f"Yapay zeka tek bir kelime söyledi: **{w.upper()}**.",
            lambda w: f"**{w.upper()}** verisi analiz edildiğinde bulgular inanılmazdı.",
            lambda w: f'"**{w.upper()}** anomalisi tespit edildi," dedi sistem sesi soğuk bir tonla.',
            lambda w: f"**{w.upper()}** frekansında titreşen sinyal dünyadan geliyordu.",
            lambda w: f"**{w.upper()}** modülü olmadan göreve devam etmek mümkün değildi.",
            lambda w: f"Uzay istasyonunun günlüğüne son kaydedilen sözcük **{w.upper()}**'dı.",
        ],
        'outro': [
            "Evren büyüktü; insanlık küçük ama inatçıydı.",
            "Son mesaj iletildi — alacak biri olup olmadığı bilinmiyordu.",
            "Teknoloji her şeyi çözebilirdi; her şeyi — insanlığın kendisi hariç.",
        ],
    },
]

def _varied_template(word_list):
    style  = random.choice(_STORY_STYLES)
    intro  = random.choice(style['intro'])
    outro  = random.choice(style['outro'])

    patterns = style['patterns'][:]
    random.shuffle(patterns)

    sentences = [intro]
    for i, word in enumerate(word_list):
        pat = patterns[i % len(patterns)]
        sentences.append(pat(word))
    sentences.append(outro)
    return ' '.join(sentences)

# ── Seed & Init ────────────────────────────────────────────────────────────────

def seed_sample_words():
    if Word.query.count() > 0:
        return
    data = [
        ('apple',  'elma',       ['I eat an apple every morning.', 'The apple fell from the tree.']),
        ('book',   'kitap',      ['She is reading a good book.', 'The book is on the table.']),
        ('water',  'su',         ['Drink more water every day.', 'The water is very cold.']),
        ('house',  'ev',         ['They live in a big house.', 'The house has a garden.']),
        ('brain',  'beyin',      ['Use your brain to solve problems.', 'The brain never stops working.']),
        ('night',  'gece',       ['Stars shine brightly at night.', 'The night was calm and quiet.']),
        ('tiger',  'kaplan',     ['A tiger is a powerful animal.', 'The tiger hunted in the jungle.']),
        ('noble',  'soylu',      ['He had a noble character.', 'Noble actions speak louder than words.']),
        ('throw',  'atmak',      ['Throw the ball to me!', 'He can throw very far.']),
        ('dream',  'rüya',       ['I had a wonderful dream last night.', 'Follow your dream always.']),
        ('smile',  'gülümseme',  ['Her smile lit up the room.', 'Always smile, it is free!']),
        ('light',  'ışık',       ['Turn on the light please.', 'The light was too bright.']),
        ('river',  'nehir',      ['The river flows to the sea.', 'We swam in the cold river.']),
        ('brave',  'cesur',      ['Be brave in difficult times.', 'A brave person faces fear.']),
        ('cloud',  'bulut',      ['A dark cloud covered the sun.', 'Clouds bring rain.']),
        ('dance',  'dans',       ['She loves to dance every day.', 'They danced until midnight.']),
        ('eagle',  'kartal',     ['The eagle soared high above.', 'An eagle has sharp vision.']),
        ('flame',  'alev',       ['The flame burned all night.', 'Keep the flame of hope alive.']),
        ('grace',  'zarafet',    ['She moved with great grace.', 'Grace under pressure is rare.']),
        ('heart',  'kalp',       ['Follow your heart always.', 'Her heart is full of kindness.']),
        ('storm',  'fırtına',    ['A storm is coming tonight.', 'The storm passed quickly.']),
        ('sword',  'kılıç',      ['The knight carried a sword.', 'The sword was sharp and long.']),
        ('peace',  'barış',      ['We must work for peace.', 'Peace brings happiness to all.']),
        ('stone',  'taş',        ['He threw a stone in the lake.', 'The stone was very heavy.']),
        ('robin',  'kızılgerdan',['A robin sang in the tree.', 'The robin has a red breast.']),
    ]
    for eng, tur, samples in data:
        w = Word(eng_word=eng, tur_word=tur)
        db.session.add(w)
        db.session.flush()
        for s in samples:
            db.session.add(WordSample(word_id=w.id, sample=s))
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        seed_sample_words()
    app.run(debug=False, port=5001)
