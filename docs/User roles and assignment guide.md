# Gramaswaraj application user roles and assignment guide

Version 1.0 | 2 November 2026

Prepared for Gramaswaraj administrators and staff. This guide describes the implemented Admin, Manager, Editor and User roles, how to assign them, and how they interact with facilitator personal logins. It applies after deploying the corresponding application update to register.gramaswaraj.in.

## 1 Role model

An account identifies a person who signs in. A role grants a set of actions. A scope limits those actions to the state, a district or a block. Assign both a role and a scope before asking a new staff member to start work.

Use one account per person. Choose the smallest role and geographical scope needed for that person's duties. Creating a staff account alone does not grant staff permissions. Accounts must be active, and location assignments must refer to active locations.

The four standard staff roles are Admin, Manager, Editor and User. Facilitator personal access is a separate account type linked to one approved facilitator; it is not the User staff role.

## 2 Standard role responsibilities

### Admin

Admin provides full application administration at state scope. Assign it only to people responsible for the whole system. Admin can manage accounts and roles, reset passwords, activate or deactivate accounts, change organization and system settings, manage locations, read audit records, and perform all operational staff actions.

Admin can permanently delete eligible applications through the application's existing deletion workflow. This permission does not bypass eligibility rules: approved member records cannot be deleted through the rejected application deletion action. Admin must still supply reasons, use current record versions and follow the application's confirmations.

Admin cannot be assigned district or block scope. The initial administrator account may also have a separate superuser flag that grants full access independently of its role assignments.

### Manager

Manager handles application review and approval, facilitator maintenance, ID cards, reports, training management and news review within the assigned area. A Manager can review applicant contact details as part of the review process, request corrections, and perform permitted application decisions. Managers can organize training, assign facilitators and record attendance.

A Manager cannot create staff accounts, assign roles, reset another user's password, change organization or system settings, manage the location directory, view the administration audit page or permanently delete applications. Managers can have state, district or block scope.

### Editor

Editor handles the news desk within the assigned area. Editors can view submitted news and its private media, approve or reject news and request changes through the existing review workflow. Approval records an editorial decision inside the application; it does not automatically publish to external websites or send WhatsApp messages.

Editor also includes basic dashboard, facilitator, location and training viewing. It does not grant application review, application approval, contact-review permission, facilitator modification, ID card issuance, report export, training management or administration access. An Editor cannot rewrite a facilitator's news as the author; the facilitator makes requested changes through their own portal.

Editors can have state, district or block scope.

### User

User is a read-only staff role for dashboard, facilitator, location and training viewing within the assigned area. It does not grant application access, news desk access, contact-review permission, approval, record modification, card issuance, report export, training management or administration.

User can have state, district or block scope. It is suitable for staff who need operational visibility without decision-making powers. It is not a replacement for a facilitator personal login.

## 3 Permission matrix

Yes means the role grants the capability, subject to location scope, record state and other application checks. No means the role does not grant it. Multiple active assignments can increase an account's effective permissions.

| Feature or action | Admin | Manager | Editor | User |
| --- | --- | --- | --- | --- |
| View dashboard and location information | Yes | Yes | Yes | Yes |
| View facilitator records | Yes | Yes | Yes | Yes |
| View training information | Yes | Yes | Yes | Yes |
| Review applications and applicant contacts | Yes | Yes | No | No |
| Approve applications | Yes | Yes | No | No |
| Modify facilitator records | Yes | Yes | No | No |
| Issue facilitator ID cards | Yes | Yes | No | No |
| Export reports | Yes | Yes | No | No |
| Create training and assign participants | Yes | Yes | No | No |
| Record training attendance | Yes | Yes | No | No |
| Review news and request changes | Yes | Yes | Yes | No |
| Create accounts and assign staff roles | Yes | No | No | No |
| Reset passwords and control account access | Yes | No | No | No |
| Change organization and system settings | Yes | No | No | No |
| Manage location directory | Yes | No | No | No |
| View administration audit page | Yes | No | No | No |
| Permanently delete eligible applications | Yes | No | No | No |

All signed-in users can change their own password. Viewing a module does not grant every download, export or action available within it. The matrix describes authorization capabilities; some navigation links may still be visible when opening them results in access denied.

## 4 Geographical scope

| Scope | Coverage | Required selection |
| --- | --- | --- |
| State | All locations covered by the application | No district or block |
| District | Records belonging to the selected district | District only |
| Block | Records belonging to the selected block in its district | District and matching block |

The form restricts Admin to state scope, filters blocks by district and requires the appropriate location fields. The server independently validates assignments even if browser scripting is disabled. An inactive district, block or parent state cannot provide an active location-based assignment.

Example: a Manager assigned to Thrissur district can approve eligible applications within Thrissur, but not applications in another district. Adding a state-level User assignment does not extend the Manager's approval permission statewide. Role and location are evaluated together for each action.

Some directory information is shared reference information; selecting a district scope is not a promise that every location name is hidden elsewhere in the interface.

## 5 Create and assign a staff account

1. Sign in with an Admin account or an existing Super Admin account.
2. Open Administration, then Accounts and roles.
3. Read the role guide and choose the responsibility and area for the person.
4. Under Create staff account, enter a unique username, email, initial password and matching confirmation. The password must contain 12 to 256 characters. Record a reason for creating the account.
5. Select Create account. Find the account using the username or email search.
6. Expand the account and go to Role assignments.
7. Choose Admin, Manager, Editor or User. User is the initial selection to avoid accidentally granting administrative access.
8. Choose the scope. For district scope select the district; for block scope select both district and block.
9. Enter the assignment reason and select Assign role.
10. Share the username and initial password privately with the account owner. Ask the owner to sign in and change the password immediately.

Identical active role and location assignments are rejected. Use an assignment reason that explains the actual responsibility, such as District application approval responsibility, rather than an unrelated note.

No person is automatically promoted when this update is deployed. The administrator chooses which account receives each role.

## 6 Change or revoke a role

Open the account in Accounts and roles. Existing assignments show the role, scope and district or block names. To remove an assignment, enter a removal reason and select Remove role. Add the replacement assignment if the person's duties have changed.

Permissions combine across active assignments. Adding User to an existing Manager account does not downgrade the account; remove the Manager assignment to remove those privileges. Review every assignment when moving a person between districts or reducing their responsibilities.

The application checks account revisions to prevent an older page from overwriting newer changes. If an account changed message appears, reload and review the current assignments before trying again.

The application prevents removing the final active account-management administrator. The initial superuser flag is independent of assigned roles: removing a scope assignment from that initial account does not remove its superuser powers. For reassignment or offboarding of that account, establish another administrator first and use the supported account access controls.

## 7 Passwords and account access

New accounts must change the initial password at first login. A password reset also requires a change at the next login and ends existing sessions. Passwords are stored as hashes; the application cannot display a user's current password.

To reset another account, open it, enter and confirm a new initial password, provide the reset reason, and select Reset password and end sessions. Use Change password for your own password.

To suspend access, clear Account active, record a reason and select Update access. Deactivation ends sessions. An administrator cannot deactivate their own account through this form. Reactivation restores the account's existing active assignments, so review those assignments before reactivating it.

Share temporary passwords through a private channel. Do not put passwords in role assignment reasons, audit notes, screenshots or this guide.

## 8 Facilitator personal logins

Allocate a personal login from the approved facilitator's profile using its login allocation controls. Each personal account is linked to one facilitator. The facilitator changes the temporary password at first login and then uses My profile, My news and My trainings.

The personal portal provides access to the facilitator's own profile, available current ID card, training assignments and attendance, and their own news submission workflow. News can include images and an MP4 video up to 1 GB, subject to file validation and storage availability. Personal access does not grant staff authority over other facilitators or applications.

Personal facilitator accounts cannot receive staff roles. If the same person also needs administrative duties, create a separate staff account with its own unique username and email and assign the necessary role there. Keep the two purposes distinct when reviewing access.

## 9 Existing role compatibility

Existing assignments remain valid; this release does not migrate or remove them. The older specialist roles remain available for compatibility.

| Existing role | Relationship to the standard model |
| --- | --- |
| SUPER_ADMIN | Same capability set as Admin with state scope |
| STATE_ADMIN | Operational management plus organization settings and audit; state scope |
| DISTRICT_ADMIN | Operational management restricted to district scope |
| BLOCK_COORDINATOR | Application and news review plus training management; block scope; no application approval |
| REVIEWER | Application and news review without approval or operational management |
| ID_CARD_OPERATOR | Basic viewing plus card issuance |
| VIEWER | Same basic viewing capabilities as User |

Use the four standard roles for new assignments unless a narrower specialist role is specifically needed. Do not replace an existing specialist assignment without checking which permissions the replacement would add or remove.

## 10 Recommended assignment examples

| Responsibility | Suggested role | Suggested scope |
| --- | --- | --- |
| Application owner and account administrator | Admin | State |
| Statewide operations coordinator | Manager | State |
| District application and facilitator coordinator | Manager | District |
| Block operations coordinator who must approve applications | Manager | Block |
| District news review team | Editor | District |
| Staff member needing read-only district visibility | User | District |
| Registered facilitator submitting news and attending training | Personal facilitator login | Own facilitator record |

Manager includes approval authority. Where approval is not part of a person's duties, use an appropriate narrower legacy specialist role rather than granting Manager automatically.

## 11 Access review and troubleshooting

Review active accounts and their assignments when duties change or staff leave. Check the account owner, geographical scope, active status and all combined assignments. Use the audit page to inspect recorded account changes and reasons. These are operating recommendations, not an automated review schedule.

If access is denied, verify the account is active, has an appropriate active assignment, and has completed its password change. Check the record's district and block against the assignment, and confirm the location hierarchy is active. A Manager, Editor or User cannot manage accounts; ask an Admin to perform account changes.

If a role seems too powerful, check for another assignment or the initial superuser flag. If the account opens only My profile, it is a linked facilitator personal account and must remain separate from staff administration.

## 12 Deployment and validation

Deploy the latest main branch with Hostinger's existing node-app configuration. These roles use the existing scope table and require no database schema version change. Validate with separate test accounts for each role and check both allowed actions and rejected actions outside the assigned area before allocating production responsibilities.

Implementation reference: node-app/src/policies.js defines capabilities and scope evaluation; node-app/src/administration.js validates assignments, records reasons and protects the final administrator. Authorization is enforced on the server, not merely by hiding interface controls.
