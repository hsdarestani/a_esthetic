# GOÄ reference validation — restricted to draft/synthetic testing

The supplied rendered calculator HTML contains the actual implementation, and the supplied screenshot shows one synthetic Botox example. It is UI/behavior evidence, not a medical or accounting authority. No supplied HTML, screenshot, identity or proprietary code is copied into this public repository.

Independent reference check (official statute):
- https://www.gesetze-im-internet.de/go__1982/anlage.html — points 1=80, 5=80, 250=40, 252=40, 268=130, 2442=900. Section A explicitly includes 250, with a special ordinary factor limit of 2.5 rather than 3.5. The 1.8 threshold requires clinical review/justification when exceeded.
- https://www.gesetze-im-internet.de/go__1982/__5.html — point value €0.0582873, documented performance-based factors and statutory thresholds.
- https://www.gesetze-im-internet.de/go__1982/__2.html — deviations require a qualifying written agreement made before service; production deviations are not supported.
- https://www.gesetze-im-internet.de/go__1982/__4.html and https://www.gesetze-im-internet.de/go__1982/__6.html — independent services, actual performance and analog equivalence; no automatic treatment-to-code mapping.
- https://www.gesetze-im-internet.de/go__1982/__10.html and https://www.gesetze-im-internet.de/go__1982/__12.html — eligible actual expenses, evidence, invoice content and justification.
- https://www.gesetze-im-internet.de/ustg_1980/__4.html and https://www.gesetze-im-internet.de/ustg_1980/__12.html — tax exemption for qualifying medical care; explicit tax classification required.

Observed sample: gross EUR 236.00, material EUR 95.52, medical EUR 102.80, principal fee EUR 81.36, displayed derived factor 3.4896, VAT EUR 19.53 + 18.15. The supplied calculator works backwards from a desired gross total and can force a VAT-cent reconciliation. Its aggregate residual differs from the app's individual fee rounding (10 x EUR 8.14 = EUR 81.40 at a two-decimal factor 3.49). Therefore the sample is reconciled in an isolated read-only synthetic reference fixture, never used to set live fees or to alter VAT to hit a total. The draft engine performs forward computation, uses official points/category for its six verified codes, and explicitly distinguishes other manual draft codes from the verified catalog.

Mandatory physician/accounting approval before real invoicing: correct procedure selection and repeatability (including 1/5 restrictions), actual injections and quantities, analog equivalence for PRP and other nonlisted services, applicability of 2442 to fillers, all clinical fee factors/reasons, eligibility and proof of actual materials, individual vs aggregate rounding and VAT treatment, invoice issuer/date/numbering and legally acceptable PDF. The source's defaults are not approval. Production issuance remains closed; synthetic TEST-GOAE numbering is the only simulated finalization.
