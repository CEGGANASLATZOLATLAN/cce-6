"""
cegganaslatzolatlan kullanıcısına 35 günlük gerçekçi kullanım verisi ekler.
"""
import random
from datetime import date, datetime, timedelta
from app import app, db, User, Word, UserWordProgress, QuizAnswer

STAGE_DAYS = {1: 1, 2: 7, 3: 30, 4: 90, 5: 180, 6: 365}
USERNAME   = 'cegganaslatzolatlan'
DAYS_BACK  = 35
TODAY      = date.today()

STAGE_DIST = [
    (7, 38),
    (6, 18),
    (5, 22),
    (4, 28),
    (3, 35),
    (2, 42),
    (1, 38),
    (0, 22),
]
TOTAL_WORDS = sum(n for _, n in STAGE_DIST)

def rand_day(start, end):
    return TODAY - timedelta(days=random.randint(start, end))

def main():
    with app.app_context():
        user = User.query.filter_by(username=USERNAME).first()
        if not user:
            print(f"❌ Kullanıcı bulunamadı: {USERNAME}")
            return
        uid = user.id
        print(f"👤 {USERNAME} (ID:{uid}) bulundu")

        QuizAnswer.query.filter_by(user_id=uid).delete()
        UserWordProgress.query.filter_by(user_id=uid).delete()
        db.session.commit()
        print("🗑  Eski veriler temizlendi")

        all_words = Word.query.all()
        random.shuffle(all_words)
        pool = all_words[:TOTAL_WORDS]

        idx = 0
        progress_objs = []

        for stage, count in STAGE_DIST:
            for w in pool[idx:idx+count]:
                p = UserWordProgress(user_id=uid, word_id=w.id)

                if stage == 0:
                    p.stage              = 0
                    p.first_correct_date = None
                    p.next_review        = None
                    p.introduced_date    = rand_day(5, DAYS_BACK)
                    p.last_reviewed      = rand_day(1, 6)
                    p.is_learned         = False

                elif stage == 7:
                    first = rand_day(DAYS_BACK, DAYS_BACK + 5)
                    p.stage              = 6
                    p.first_correct_date = first
                    p.next_review        = first + timedelta(days=STAGE_DAYS[6])
                    p.introduced_date    = first
                    p.last_reviewed      = rand_day(1, 8)
                    p.is_learned         = True

                else:
                    days_since = STAGE_DAYS.get(stage, 1)
                    first = rand_day(days_since + 2, days_since + 15)
                    next_rev = first + timedelta(days=STAGE_DAYS[stage])

                    intro_start = min(days_since + 10, DAYS_BACK)
                    intro_end   = DAYS_BACK
                    if intro_start >= intro_end:
                        intro_start = max(1, intro_end - 3)

                    p.stage              = stage
                    p.first_correct_date = first
                    p.next_review        = next_rev
                    p.introduced_date    = rand_day(intro_start, intro_end)
                    p.last_reviewed      = rand_day(1, min(days_since + 2, DAYS_BACK))
                    p.is_learned         = False

                db.session.add(p)
                progress_objs.append((p, w, stage))
            idx += count

        db.session.commit()
        print(f"📈 {TOTAL_WORDS} kelime için ilerleme kaydı oluşturuldu")

        answer_count = 0

        for days_ago in range(DAYS_BACK, 0, -1):
            quiz_date = TODAY - timedelta(days=days_ago)
            weekday = quiz_date.weekday()
            if weekday < 5:
                n_questions = random.randint(9, 14)
            else:
                n_questions = random.randint(5, 9)

            day_words = random.sample(pool, min(n_questions, len(pool)))

            for w in day_words:
                base_rate = 0.58 + (DAYS_BACK - days_ago) * 0.004
                is_correct = random.random() < min(base_rate, 0.78)

                prog = next((p for p, ww, _ in progress_objs if ww.id == w.id), None)
                stage_b = prog.stage if prog else 0

                qa = QuizAnswer(
                    user_id      = uid,
                    word_id      = w.id,
                    is_correct   = is_correct,
                    quiz_date    = quiz_date,
                    answered_at  = datetime.combine(quiz_date, datetime.min.time()) + timedelta(
                        hours=random.randint(18, 22),
                        minutes=random.randint(0, 59)
                    ),
                    stage_before = stage_b,
                )
                db.session.add(qa)
                answer_count += 1

        db.session.commit()
        print(f"📝 {answer_count} quiz cevabı oluşturuldu ({DAYS_BACK} gün)")

        learned = sum(1 for _, _, s in progress_objs if s == 7)
        in_prog = sum(1 for _, _, s in progress_objs if 1 <= s <= 6)
        failed  = sum(1 for _, _, s in progress_objs if s == 0)
        all_ans = QuizAnswer.query.filter_by(user_id=uid).all()
        correct = sum(1 for a in all_ans if a.is_correct)
        pct     = round(correct / len(all_ans) * 100) if all_ans else 0

        print("\n── Özet ──────────────────────────────")
        print(f"  Öğrenildi   : {learned} kelime")
        print(f"  Devam ediyor: {in_prog} kelime")
        print(f"  Başarısız   : {failed} kelime")
        print(f"  Toplam cevap: {len(all_ans)}")
        print(f"  Doğruluk    : %{pct}")
        print("──────────────────────────────────────")
        print("✅ Demo verisi hazır!")

if __name__ == '__main__':
    main()
