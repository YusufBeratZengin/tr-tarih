# Security policy

## Supported versions

Security fixes target the latest 0.1.x version. The project is alpha software.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/YusufBeratZengin/tr-tarih/security/advisories/new). Do not open a public issue for a suspected vulnerability. If private reporting is unavailable, ask the maintainer to enable it without disclosing exploit details publicly.

Describe the affected version, impact and a minimal reproduction using synthetic data. Never submit credentials, personal information or private input. The maintainer will assess the report and coordinate disclosure and a fix privately.

The library performs no networking or file persistence. Applications must decide which inputs to accept, how to handle parse failures and where CLI/JSON output is stored.
