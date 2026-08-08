# A+ Esthetic – Store Release Contract

## Product positioning

A+ Esthetic is the digital customer club of A+ Esthetic. The app is for customer relationship and loyalty features such as membership, benefits, rewards, customer communication, appointment organisation and account/privacy management.

The app itself does not provide diagnosis, medical advice, treatment recommendations, dosage guidance, clinical decision support or healthcare services. Medical services, where separately offered at the practice, are provided independently by qualified professionals and are not performed by the app.

## Store category / wording

Use customer-club, lifestyle, loyalty and service wording in Google Play and App Store metadata. Do not market the app as a healthcare product or diagnostic tool.

Suggested short description (DE):

> Der digitale A+ Esthetic Kundenclub für Mitgliedschaft, Vorteile, Termine, Rewards und direkten Kontakt.

Suggested description themes:

- digitale Mitgliedskarte
- Club-Vorteile und Rewards
- Terminorganisation
- persönliche Mitteilungen und Kundenservice
- Verwaltung von Profil und Einwilligungen

## Stable identifiers

- App name: `A+ Esthetic`
- Android application ID: `de.aplusesthetic.app`
- iOS bundle ID: `de.aplusesthetic.app`
- Production URL: `https://esthetic.smarbiz.sbs`

Do not change the Android application ID or iOS bundle ID after store records are created.

## Public store URLs

The production website must expose public, no-login pages for:

- Datenschutz / privacy policy
- Impressum
- Support / contact
- Account deletion request

The store declarations must match the data and features that are actually enabled in the release being submitted.

## Release principle

Before every store build run:

```bash
npm run store:check
```

A release must not introduce store-facing wording that presents A+ Esthetic as a medical or healthcare app.
