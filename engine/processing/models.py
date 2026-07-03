"""Processing models — reserved for future infrastructure models.

This module exists so that Django's emit_post_migrate_signal includes
engine.processing.  Without models_module, post_migrate is never sent and the
processing Q2 schedule (ID 4) would never be auto-created.
"""
