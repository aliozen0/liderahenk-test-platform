# Registration Orchestrator

Bu servis urun mantigini patch'lemek icin degil, registration truth'u disaridan izlemek ve raporlamak icin vardir.

## Sorumluluklar

- LDAP, XMPP, `c_agent`, dashboard ve computer tree arasindaki tutarliligi gozlemlemek
- startup race condition semptomlarini kayda gecirmek
- platform acceptance ve golden parity icin kanit uretmek

## Bilincli Sinir

Bu servis stock LiderAhenk davranisini override etmez. Yalnizca:

- snapshot alir
- drift raporlar
- artifact yazar

Gercek mutasyon gerekiyorsa bu bootstrap/provisioning katmaninda cozulmelidir.
