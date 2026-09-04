# A+ Esthetic – Store data declaration baseline

This file is the release baseline for Google Play Data safety and Apple App Privacy. It must be reviewed against the exact release before submission.

## Product purpose

A+ Esthetic is a customer club / loyalty and customer-service app. It also provides a secure document area through which an authenticated customer can access documents shared by A+ Esthetic and can voluntarily upload documents, photos, forms or notes to the practice record.

The app does not provide diagnosis, medical advice, treatment recommendations, dosage guidance or clinical decision support.

## Data used by the customer-club release

### Account / identifiers

Possible values:
- username / internal user ID
- name, if stored on the member account
- phone number entered in profile
- email address associated with the login account

Purpose:
- account operation
- customer support
- membership identification
- security

### Club and loyalty data

Possible values:
- membership number and tier
- A+ Coins / internal club credit
- rewards and reward redemptions
- referral codes and referral status
- active club packages / benefits

Purpose:
- provide customer-club functionality
- fraud/security controls
- customer support

### Appointment organisation

Possible values:
- requested date/time
- selected service/category where enabled
- assigned contact/staff member where enabled
- optional customer note
- request status

Purpose:
- organise customer appointments and customer service

This feature is organisational. The mobile app is not a diagnostic or treatment system.

### Shared patient documents / health information

Possible values, only when the feature is used:
- documents, images, forms or notes voluntarily uploaded by the customer
- documents or information made available to the authenticated customer by A+ Esthetic
- file metadata such as title, document type, file name, size and upload date
- appointment association where a document is linked to an appointment
- information contained in an uploaded or shared document, which may include health information
- consent evidence for processing customer-uploaded health information

Purpose:
- secure document exchange between the authenticated customer and A+ Esthetic
- make customer-accessible practice documents available in the app
- support practice documentation and customer service
- associate documents with the correct customer record
- security, access control and auditability

Important release rules:
- access is account-scoped and authenticated
- internal practice notes are not automatically visible to the customer
- the practice explicitly controls whether a clinic-originated record is shared to the customer account
- customer uploads are stored in the same protected practice record and are visible in the customer's shared timeline
- removing a customer-uploaded item from the app view does not automatically erase information that the practice must retain for documentation or legal purposes
- this data is not used by the app to diagnose, recommend treatment, calculate dosage or make automated clinical decisions
- this data is not used for third-party advertising or cross-app tracking

For Apple App Privacy / Google Play Data safety, the exact store answers must disclose health information and user content/files when this shared-patient-record feature is enabled in the submitted binary.

### Customer messages

Possible values:
- messages sent to A+ Esthetic customer support
- message timestamps and thread status

Purpose:
- customer support and service communication

### Consent / preference data

Possible values:
- marketing preference
- health-data/document-processing consent where applicable
- consent version/timestamp where a consent is used
- technical evidence needed to demonstrate the choice

Purpose:
- honour customer preferences
- compliance and auditability

### Notifications and device data

Possible values:
- push notification device token
- mobile platform and app version
- notification delivery/read state

Purpose:
- deliver requested service notifications
- provide the in-app Notification Center
- maintain notification reliability and security

### Security / technical data

Possible values:
- IP address in security/audit events
- user agent
- session/security metadata

Purpose:
- authentication
- abuse prevention
- security logging

## Explicitly outside the customer-club release

The store-facing customer club must not intentionally use data for automated diagnosis, therapy, dosage, clinical decision-making or personalised medical recommendations.

The presence of a secure shared patient-document area does not change this product rule: it is an access/document-exchange feature, not a diagnostic feature.

Legacy database models that are not part of the customer product must remain disabled and must not be used as a reason to market the app as a diagnostic or clinical decision-support product.

## Third-party advertising / tracking

Do not add advertising SDKs or cross-app tracking without updating this file, the public privacy policy, Apple App Privacy and Google Play Data safety before release.
