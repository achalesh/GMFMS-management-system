# Hostinger staging deployment

This package is the Node migration preview. MySQL integration, existing Django data migration and production card templates still require validation before switching gramaswaraj.in.

1. Create a dedicated, empty MySQL database and a staging Web App. Do not point this build at the existing Django database. Keep a backup of the existing website and database.
2. Upload `release/gramaswaraj-hostinger.zip`. Its root contains package.json. Choose Node 24, framework Other, build command `npm run build`, start command `npm start`, and port 3000. Hostinger may detect these automatically. Use the equivalent pnpm commands when the lockfile is selected.
3. Enter environment variables in hPanel using `.env.production.example` as a field reference. Generate a random session secret locally. Encode special characters in the MySQL URL credentials. Never upload an actual .env file.
4. For the first staging deployment only, set RUN_MIGRATIONS=true. To create the first administrator, also set BOOTSTRAP_ADMIN=true and ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD (12–256 characters). Bootstrap fails on duplicate accounts; it does not reset existing passwords. Remove these switches and all three ADMIN variables after successful initialization, then redeploy. Bootstrap credentials must be entered privately in hPanel.
5. Check `/health/live/` and `/health/ready/`. Test login, secure cookies, registration with private uploads, correction links, approval, account permissions, card QR verification and exports against MySQL. The upload column uses base64: ensure max_allowed_packet supports at least 8 MB. Verify reverse proxy forwarding before setting TRUST_PROXY_HOPS=1; never trust an unverified proxy chain.
6. Validate backups and a restore in staging, and arrange regular `node scripts/maintenance.js` runs with a supported scheduling service. Business hosting scheduling availability must be checked separately.
7. Migrate existing Django records using a reviewed migration process (not included yet). Reconcile counts, assignments, consents, appointments and private files. Only then set APP_ORIGIN=https://gramaswaraj.in and connect the main domain. Changing the origin makes previously generated card sources outdated; reissue cards after final domain selection.

Data and uploads reside in MySQL, not in the deploy filesystem. The ZIP excludes local databases, session secrets, uploads and node_modules. Account creation, role changes, settings changes and password resets are available through Administration. New staff accounts must change their temporary password. Master location editing and email password recovery remain future work.

Official references: [Node deployment](https://www.hostinger.com/support/how-to-deploy-a-nodejs-website-in-hostinger/), [build troubleshooting](https://www.hostinger.com/support/fix-failed-to-build-application-error-hostinger-node-js/), [environment variables](https://www.hostinger.com/support/how-to-add-environment-variables-during-node-js-application-deployment/).

See MIGRATION.md for the verified Django snapshot rehearsal, unresolved card/appointment/draft mapping and MySQL checks.
