from infrastructure.repositories.analytics_repo import AnalyticsRepository
from core.interfaces.content_generator import ContentGenerator


class AnalyticsService:

    def __init__(self, generator: ContentGenerator):
        self._repo      = AnalyticsRepository()
        self._generator = generator

    async def weekly_summary(self, student_id: str) -> dict:
        data = self._repo.get_student_weekly_summary(student_id)

        # Generate plain-language summary using LLM
        if data["subjects"]:
            best    = max(data["subjects"], key=lambda x: x["avg_mastery"])
            weakest = min(data["subjects"], key=lambda x: x["avg_mastery"])
            grade   = data.get("grade_level", 9)
            prompt  = (
                f"Write a short, encouraging weekly progress summary for a Grade {grade} student.\n"
                f"Overall mastery: {data['overall_mastery']*100:.0f}%\n"
                f"Topics mastered: {data['topics_mastered']}/{data['topics_assessed']}\n"
                f"Active topics this week: {data['active_topics_this_week']}\n"
                f"Strongest subject: {best['subject']} ({best['avg_mastery']*100:.0f}%)\n"
                f"Needs work: {weakest['subject']} ({weakest['avg_mastery']*100:.0f}%)\n"
                "Write 2-3 sentences. Be positive and specific. Mention Ethiopian context if relevant."
            )
            try:
                data["summary"] = await self._generator._call_raw(prompt)
            except Exception:
                data["summary"] = (
                    f"Overall mastery is {data['overall_mastery']*100:.0f}%. "
                    f"Strongest in {best['subject']}, needs focus on {weakest['subject']}."
                )
        else:
            data["summary"] = "No activity recorded yet. Encourage the student to start their first quiz!"

        return data

    async def at_risk_students(self, subject_id: str, limit: int = 50, offset: int = 0) -> dict:
        students = self._repo.get_at_risk_students(subject_id, limit=limit, offset=offset)
        high_risk   = [s for s in students if s["risk_level"] == "HIGH"]
        medium_risk = [s for s in students if s["risk_level"] == "MEDIUM"]

        return {
            "subject_id": subject_id,
            "high_risk_count": len(high_risk),
            "medium_risk_count": len(medium_risk),
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "recommendations": self._intervention_tips(high_risk),
        }

    async def class_performance(self, subject_id: str, limit: int = 50, offset: int = 0) -> dict:
        return self._repo.get_class_performance(subject_id, limit=limit, offset=offset)

    @staticmethod
    def _intervention_tips(high_risk: list) -> list[str]:
        if not high_risk:
            return []
        tips = [f"Schedule 1-on-1 sessions for {len(high_risk)} high-risk student(s)."]
        critical = [s for s in high_risk if s["critical_topics"] > 3]
        if critical:
            tips.append(f"{len(critical)} student(s) have 3+ critical topics — consider remedial group sessions.")
        inactive = [s for s in high_risk if not s["last_active"]]
        if inactive:
            tips.append(f"{len(inactive)} student(s) have never attempted a quiz — contact parents.")
        return tips
