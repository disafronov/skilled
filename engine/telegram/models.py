import secrets
from datetime import datetime

from django.db import models
from django.db.models import Q

from ..common.fields import EncryptedCharField


def generate_webhook_secret() -> str:
    """Generate a 32-char hex string for X-Telegram-Bot-Api-Secret-Token."""
    return secrets.token_hex(16)


class JobQuerySet(models.QuerySet["Job"]):
    """QuerySet methods for Job pipeline state queries."""

    def stale_processing(self, cutoff: datetime) -> "JobQuerySet":
        """Processing started but not finished — candidates for re-queue."""
        return self.filter(
            processing_started_at__lt=cutoff,
            processing_finished_at__isnull=True,
            processing_error__isnull=True,
        )

    def ready_for_processing(self) -> "JobQuerySet":
        """Jobs waiting for processing (never started, no processing error)."""
        return self.filter(
            processing_started_at__isnull=True,
            processing_finished_at__isnull=True,
            processing_error__isnull=True,
        )

    def ready_for_delivery(self) -> "JobQuerySet":
        """Jobs with processing output ready to be sent to the user."""
        return self.filter(
            processing_finished_at__isnull=False,
            delivery_started_at__isnull=True,
            delivery_finished_at__isnull=True,
        ).exclude(raw_output__isnull=True, processing_error__isnull=True)


class Bot(models.Model):
    """Telegram endpoint / transport identity."""

    name = models.CharField(max_length=255, unique=True)
    telegram_api_token = EncryptedCharField(max_length=512)

    webhook_secret = EncryptedCharField(
        max_length=64,
        default=generate_webhook_secret,
    )

    enabled = models.BooleanField(default=True)
    telegram_update_offset = models.IntegerField(default=0)
    webhook_enabled_at = models.DateTimeField(null=True, blank=True)
    webhook_disabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bot"
        verbose_name_plural = "Bots"
        app_label = "telegram"
        db_table = "telegram_bot"

    def __str__(self) -> str:
        return self.name

    def rotate_webhook_secret(self) -> None:
        """Generate a new webhook_secret and invalidate current webhook registration."""
        type(self).objects.filter(pk=self.pk).update(
            webhook_secret=generate_webhook_secret(),
            webhook_enabled_at=None,
        )


class Job(models.Model):
    """A single pipeline execution artifact — from Telegram message to response."""

    bot = models.ForeignKey(Bot, on_delete=models.PROTECT)
    reply_target = models.TextField()
    reply_to_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    raw_input = models.TextField()
    raw_output = models.TextField(null=True, blank=True)
    processing_error = models.TextField(null=True, blank=True)
    delivery_error = models.TextField(null=True, blank=True)

    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_finished_at = models.DateTimeField(null=True, blank=True)
    delivery_started_at = models.DateTimeField(null=True, blank=True)
    delivery_finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        app_label = "telegram"
        db_table = "telegram_job"
        indexes = [
            models.Index(
                fields=["created_at", "id"],
                name="tg_job_ready_processing_idx",
                condition=models.Q(
                    processing_started_at__isnull=True,
                    processing_finished_at__isnull=True,
                    processing_error__isnull=True,
                ),
            ),
            models.Index(
                fields=["processing_started_at"],
                name="tg_job_stale_processing_idx",
                condition=models.Q(
                    processing_started_at__isnull=False,
                    processing_finished_at__isnull=True,
                    processing_error__isnull=True,
                ),
            ),
            models.Index(
                fields=["processing_finished_at", "id"],
                name="tg_job_ready_delivery_idx",
                condition=models.Q(
                    processing_finished_at__isnull=False,
                    delivery_started_at__isnull=True,
                    delivery_finished_at__isnull=True,
                )
                & (
                    models.Q(raw_output__isnull=False)
                    | models.Q(processing_error__isnull=False)
                ),
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(raw_output__isnull=True)
                    | models.Q(processing_finished_at__isnull=False)
                ),
                name="tg_job_raw_output_requires_processing_finished",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(processing_finished_at__isnull=True)
                    | models.Q(raw_output__isnull=False)
                    | models.Q(processing_error__isnull=False)
                ),
                name="tg_job_processing_finished_requires_result_or_error",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(processing_finished_at__isnull=True)
                    | models.Q(processing_started_at__isnull=False)
                ),
                name="tg_job_processing_finished_requires_started",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(delivery_started_at__isnull=True)
                    | (
                        models.Q(processing_finished_at__isnull=False)
                        & (
                            models.Q(raw_output__isnull=False)
                            | models.Q(processing_error__isnull=False)
                        )
                    )
                ),
                name="tg_job_delivery_started_requires_output",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(delivery_finished_at__isnull=True)
                    | models.Q(delivery_started_at__isnull=False)
                ),
                name="tg_job_delivery_finished_requires_started",
            ),
        ]

    def __str__(self) -> str:
        return f"Job #{self.pk} [{self.bot.name}]"


class IntakeBuffer(models.Model):
    """Mutable accumulator for consecutive Telegram messages before Job creation."""

    bot = models.ForeignKey(Bot, on_delete=models.CASCADE)
    chat_id = models.CharField(max_length=255)
    reply_to_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    text = models.TextField()
    message_count = models.PositiveIntegerField(default=1)
    last_message_ts = models.PositiveBigIntegerField()
    last_received_at = models.DateTimeField()
    flushed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Intake Buffer"
        verbose_name_plural = "Intake Buffers"
        app_label = "telegram"
        db_table = "telegram_intakebuffer"
        constraints = [
            models.UniqueConstraint(
                fields=["bot", "chat_id"],
                condition=Q(flushed_at__isnull=True),
                name="tg_uniq_open_intake_buffer_per_bot_chat",
            ),
        ]

    def __str__(self) -> str:
        return f"IntakeBuffer #{self.pk} [{self.bot.name}] #{self.chat_id}"
