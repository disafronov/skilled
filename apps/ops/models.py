"""Operational models — reserved for future infrastructure models.

This module exists so that Django's emit_post_migrate_signal includes
apps.ops.  Without models_module, post_migrate is never sent and the
Q2 cleanup schedule (ID 5) would never be auto-created.
"""
