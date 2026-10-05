-- Run as migration owner after every release. Runtime role must already exist.
GRANT CONNECT ON DATABASE gmfms TO gmfms_app;
GRANT USAGE ON SCHEMA public TO gmfms_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gmfms_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gmfms_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_auditlog FROM gmfms_app;
REVOKE ALL ON TABLE django_migrations FROM gmfms_app;
GRANT SELECT ON TABLE django_migrations TO gmfms_app;
