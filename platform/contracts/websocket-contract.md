# WebSocket Contract

## Scope

Stock Lider UI ile `liderapi` arasindaki `/liderws/` kanali.

## Routing

- Public UI endpoint: `/liderws/**`
- Reverse proxy target: `liderapi:8080/liderws/**`
- SockJS fallback endpoint'leri ayni prefix altinda korunur

## Delivery Rules

- websocket yoksa SockJS fallback kabul edilir
- ilk websocket denemesi kapansa bile durum akisi fallback transport ile surmelidir
- task ve policy durumlari ayni kullanici kanalina duser

## Required Semantics

- login sonrasi task status subscription kurulabilmeli
- `EXECUTE_TASK` ve `EXECUTE_POLICY` sonucunda UI toast ve status guncellemesi dusmeli
- proxy timeout veya upgrade basarisizligi sessiz veri kaybina donusmemeli

## Evidence

- browser devtools websocket guncellemesi
- nginx access log upgrade veya fallback istegi
- liderapi task status domain state
