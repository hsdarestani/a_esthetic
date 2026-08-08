# A+ Esthetic – Store data declaration baseline

This file is the release baseline for Google Play Data safety and Apple App Privacy. It must be reviewed against the exact release before submission.

## Product purpose

A+ Esthetic is a customer club / loyalty app. The app does not provide diagnosis, medical advice, treatment recommendations, clinical decision support or healthcare services.

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

### Customer messages

Possible values:
- messages sent to A+ Esthetic customer support
- message timestamps and thread status

Purpose:
- customer support and service communication

### Consent / preference data

Possible values:
- marketing preference
- consent version/timestamp where a consent is used
- technical evidence needed to demonstrate the choice

Purpose:
- honour customer preferences
- compliance and auditability

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

The store-facing customer club must not intentionally collect or use data for diagnosis, therapy, dosage, clinical decision-making or personalised medical recommendations.

Legacy database models that are not part of the customer product must remain disabled and must not be used as a reason to market or classify the app as a healthcare product.

## Third-party advertising / tracking

Do not add advertising SDKs or cross-app tracking without updating this file, the public privacy policy, Apple App Privacy and Google Play Data safety before release.
