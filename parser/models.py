from django.db import models


class ExerciseRecord(models.Model):
    record_id = models.CharField(max_length=20, unique=True, verbose_name="ID записи")
    exercise_id = models.CharField(max_length=20, db_index=True)
    activity_id = models.CharField(max_length=20)
    question_id = models.CharField(max_length=20, blank=True, default="")
    user_id = models.CharField(max_length=20, db_index=True)
    course_id = models.CharField(max_length=20, db_index=True)
    task_id = models.CharField(max_length=20, blank=True, default="")
    module_id = models.CharField(max_length=20, blank=True, default="")
    student_id = models.CharField(max_length=20, blank=True, default="")
    user_course_id = models.CharField(max_length=20, blank=True, default="")

    created_at = models.DateTimeField()
    modified_at = models.DateTimeField()
    done_at = models.DateTimeField(null=True, blank=True)
    checking_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    answer = models.TextField(blank=True, default="")
    files = models.JSONField(default=list, blank=True)
    check_comment = models.TextField(blank=True, default="")

    exercise_title = models.CharField(max_length=500)
    exercise_description = models.TextField(blank=True, default="")
    exercise_instruction = models.TextField(blank=True, default="")
    exercise_attempts = models.CharField(max_length=10, blank=True, default="")
    exercise_min_result = models.CharField(max_length=10, blank=True, default="")

    task_title = models.CharField(max_length=500)
    task_index = models.CharField(max_length=50, blank=True, default="")
    module_title = models.CharField(max_length=500, blank=True, default="")
    course_title = models.CharField(max_length=500, blank=True, default="")

    user_name = models.CharField(max_length=300)
    user_bio = models.TextField(blank=True, default="")
    user_email = models.EmailField(max_length=300, blank=True, default="")
    user_region_code = models.CharField(max_length=200, blank=True, default="")
    user_timezone = models.CharField(max_length=10, blank=True, default="")
    user_progress = models.CharField(max_length=10, blank=True, default="")
    user_birthday = models.DateField(null=True, blank=True)

    operator = models.CharField(max_length=300, blank=True, default="")

    checked = models.BooleanField(default=False)
    passed = models.BooleanField(default=False)
    skip = models.BooleanField(default=False)
    checking = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    error = models.BooleanField(default=False)
    invisible = models.BooleanField(default=False)
    favorite = models.BooleanField(default=False)

    result_score = models.CharField(max_length=10, blank=True, default="")
    duration = models.CharField(max_length=10, blank=True, default="")
    stars = models.CharField(max_length=5, blank=True, default="0")
    min_score = models.CharField(max_length=5, blank=True, default="")
    format = models.CharField(max_length=5, blank=True, default="")

    flow_num = models.CharField(max_length=10, blank=True, default="")
    chat_id = models.CharField(max_length=50, blank=True, default="")
    manual_check = models.BooleanField(default=False)
    check_minutes = models.CharField(max_length=10, blank=True, default="")

    raw_data = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exercise record"
        verbose_name_plural = "Exercise records"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["exercise_id", "user_id"]),
            models.Index(fields=["user_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_name} – {self.task_title} ({self.record_id})"

    @classmethod
    def from_api_response(cls, data: dict) -> "ExerciseRecord":
        def _str(val: object) -> str:
            return str(val) if val is not None else ""

        def _bool(val: object) -> bool:
            if isinstance(val, str):
                return val.lower() in ("1", "true", "yes")
            return bool(val)

        def _parse_dt(val: object):
            from django.utils import timezone
            import datetime as dt_mod
            if not val:
                return None
            try:
                naive = dt_mod.datetime.strptime(_str(val)[:19], "%Y-%m-%d %H:%M:%S")
                return timezone.make_aware(naive)
            except (ValueError, TypeError):
                return None

        def _parse_date(val: object):
            import datetime as dt_mod
            if not val:
                return None
            try:
                return dt_mod.datetime.strptime(_str(val)[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return None

        def _parse_json_field(val: object):
            import json as _json
            if isinstance(val, (list, dict)):
                return val
            if isinstance(val, str) and val.strip():
                try:
                    return _json.loads(val)
                except (_json.JSONDecodeError, TypeError):
                    pass
            return val if val else []

        return cls(
            record_id=_str(data.get("id")),
            exercise_id=_str(data.get("exercise_id")),
            activity_id=_str(data.get("activity_id")),
            question_id=_str(data.get("questionId")),
            user_id=_str(data.get("user_id")),
            course_id=_str(data.get("course_id")),
            task_id=_str(data.get("taskId")),
            module_id=_str(data.get("moduleId")),
            student_id=_str(data.get("student_id")),
            user_course_id=_str(data.get("userCourseId")),
            created_at=_parse_dt(data.get("created_at")),
            modified_at=_parse_dt(data.get("modified_at")),
            done_at=_parse_dt(data.get("done_at")),
            checking_at=_parse_dt(data.get("checking_at")),
            approved_at=_parse_dt(data.get("approved_at")),
            answer=_str(data.get("answer")),
            files=_parse_json_field(data.get("files")),
            check_comment=_str(data.get("check_comment")),
            exercise_title=_str(data.get("exerciseTitle")),
            exercise_description=_str(data.get("exerciseDescription")),
            exercise_instruction=_str(data.get("exerciseInstruction")),
            exercise_attempts=_str(data.get("exerciseAttempts")),
            exercise_min_result=_str(data.get("exerciseMinResult")),
            task_title=_str(data.get("taskTitle")),
            task_index=_str(data.get("task_index")),
            module_title=_str(data.get("moduleTitle")),
            course_title=_str(data.get("courseTitle")),
            user_name=_str(data.get("userName")),
            user_bio=_str(data.get("userBio")),
            user_email=_str(data.get("userEmail")),
            user_region_code=_str(data.get("userRegionCode")),
            user_timezone=_str(data.get("userTimeZone")),
            user_progress=_str(data.get("userProgress")),
            user_birthday=_parse_date(data.get("userBirthday")),
            operator=_str(data.get("operator")),
            checked=_bool(data.get("checked")),
            passed=_bool(data.get("passed")),
            skip=_bool(data.get("skip")),
            checking=_bool(data.get("checking")),
            archived=_bool(data.get("archived")),
            approved=_bool(data.get("approved")),
            error=_bool(data.get("error")),
            invisible=_bool(data.get("invisible")),
            favorite=_bool(data.get("favorite")),
            result_score=_str(data.get("resultScore")),
            duration=_str(data.get("duration")),
            stars=_str(data.get("stars")),
            min_score=_str(data.get("minScore")),
            format=_str(data.get("format")),
            flow_num=_str(data.get("flowNum")),
            chat_id=_str(data.get("chat_id")),
            manual_check=_bool(data.get("manualCheck")),
            check_minutes=_str(data.get("check_minutes")),
            raw_data=data,
        )
