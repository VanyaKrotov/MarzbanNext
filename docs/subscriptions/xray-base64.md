# XRAY_BASE64 и plaintext share links

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Обязательная предобработка: [common.md](common.md). Общий индекс: [README.md](README.md).

## Исходники и интерфейс

Файл: [src/modules/subscription-template/generators/xray.generator.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/generators/xray.generator.service.ts).

| Метод | Назначение |
| --- | --- |
| generateConfig, строки 47–60 | Массив URI → LF-строки → необязательный Base64 |
| generateLinks, 62–81 | Фильтр формата, сборка, mapper, extended description |
| generateLink / build*Link, 83–212 | Протокольные заготовки ShareLink |
| applyTransportParams, 216–334 | Query транспорта |
| applySecurityParams, 338–426 | Query TLS/Reality |
| applyBase64Mapper / sanitizeLink, 428–474 | Изменение query и полей URI |
| serializeLink / formatAddress / buildQueryString, 476–517 | Сериализация и escaping |

Вход: `ResolvedProxyConfig[]`, `isBase64`, `isExtendedClient`. Выход generateConfig —
строка; generateLinks — список строк. В публичном render dispatcher XRAY_BASE64 всегда
использует isBase64=true и Content-Type text/plain. Plaintext используется при прямом
вызове с false; info API получает массив URI через generateLinks(..., false).
Клиентского шаблона нет.

```ts
const links = this.generateLinks(hosts, isExtendedClient);
const joined = links.join('\n');
return isBase64 ? Buffer.from(joined).toString('base64') : joined;
```

LF между URI, без завершающего LF. Base64 стандартный, с padding и без переноса строк;
исходная кодировка UTF-8. Пустой список → `''`, в обоих режимах.

## Отбор и порядок

Пропускаются hosts с `excludeFromSubscriptionTypes` containing `XRAY_BASE64`.
Здесь не проверяются isHidden/isDisabled: обычный HTTP pipeline уже отфильтровал их.
Неизвестный protocol → null. Протокол hysteria требует transport=hysteria, иначе null.
Остальные сочетания transport/security не валидируются, включая transport=hysteria
для не-hysteria protocol. Порядок URI соответствует входному массиву.
Ошибка в generateConfig даёт `''`; generateLinks сам общего try/catch не содержит.

## Протокольные URI

ShareLink: scheme, address, port, password, remark, params и optional method.

| Protocol | ShareLink | Сериализация |
| --- | --- | --- |
| vless | scheme=vless, password=protocolOptions.id | `vless://<escaped id>@<address>:<port>?<query>#<escaped remark>` |
| trojan | scheme=trojan, password=protocolOptions.password | Аналогично VLESS |
| shadowsocks | scheme=ss, method/password из protocolOptions, params={} | `ss://<base64_utf8(method:password)>@<address>:<port>#<escaped remark>` |
| hysteria | scheme=hysteria2, password=transportOptions.auth | `hysteria2://<escaped auth>@<address>:<port>/<optional ?query>#<escaped remark>` |

Shadowsocks credentials Base64 **не** Base64URL и не percent-encoded; `=` padding остаётся.
Для SS2022 весь составной пароль из resolver кодируется внутри `method:password` ещё раз.
Query у SS при сериализации игнорируется, даже если mapper добавил параметры.
У VLESS/Trojan знак `?` остаётся даже при пустом query; у Hysteria2 — только при непустом.

VLESS в params сначала добавляет truthy encryption, затем truthy flow; далее transport,
security; затем truthy streamOverrides.finalMask как `fm=JSON.stringify(finalMask)`.
Trojan добавляет только transport и security: общий finalMask сюда не переносится.
Для SS uot/transport/security исходный генератор в URI не пишет.

## Query транспорта для VLESS/Trojan

Сначала всегда добавляется `type=host.transport`.

| Transport | Дополнительные параметры и условия |
| --- | --- |
| tcp | При header: `headerType=header.type`; если type=http и request truthy, path=request.path?.join(',') ?? '', host=request.headers?.Host?.join(',') ?? '' |
| ws | Truthy path, host, heartbeatPeriod → одноимённые поля |
| httpupgrade | Truthy path, host |
| grpc | Truthy serviceName; mode всегда `multi` при multiMode=true, иначе `gun`; truthy authority |
| xhttp | Truthy path, host, mode; truthy extra → compact JSON в `extra` |
| kcp | Truthy clientMtu → mtu, clientTti → tti; congestion в ссылке отсутствует |
| hysteria | Кроме type ничего; auth/version не копируются в общий transport query |

В WS `?ed=` остаётся частью path и экранируется; разбор early data здесь отсутствует.
WS/httpupgrade headers и gRPC-настройки вне таблицы не выводятся. TCP header.request.Host
ожидается массивом: неверный runtime-тип может вызвать ошибку, автоматического исправления нет.

## Query security

Сначала всегда `security=none|tls|reality`.

| Security | Поля в порядке вставки |
| --- | --- |
| tls | sni, fp, alpn, pcs, vcn, cs |
| reality | sni, fp, pbk, sid, pqv, spx |
| none | Только security |

TLS: sni добавляется при `serverName !== null`, включая пустую строку; fp/alpn/pcs/vcn/cs
только truthy. pcs=pinnedPeerCertSha256, vcn=verifyPeerCertByName, cs=cipherSuites.
Reality: sni аналогично, fp всегда `fingerprint || chrome`, pbk=publicKey,
sid=shortId, pqv=mldsa65Verify, spx=spiderX — последние четыре только truthy.
Если неправильно сформированный raw host оставил serverName undefined, значение сначала
добавится в params, но buildQueryString затем исключит его.
ECH, session resumption, sockopt и mux в URI стандартная ветка не переносит.

## Hysteria2 отдельно

Не вызывает общие transport/security методы, поэтому нет type/security/fp/alpn query.

1. Первый `finalMask.udp` элемент с type=salamander: если его settings.password truthy,
   добавить obfs=salamander и obfs-password. Поиск останавливается на первом type,
   даже если у него нет пароля; последующий корректный элемент тогда не используется.
2. При security=tls: truthy serverName → sni, pinnedPeerCertSha256 → pinSHA256.
3. Truthy finalMask → fm с compact JSON; QUIC-параметры не переводятся в отдельные поля.

В отличие от Mihomo packetSize не превращает obfs в gecko. Pinned certificate здесь
остаётся значением pinSHA256, а не insecure=true.

## Mapper base64

Выполняется до сериализации, после стандартной сборки ShareLink.
Операции делятся на две последовательности с сохранением порядка внутри каждой:

- `to` без `$link.` → query params; flat literal keys, точка в имени не создаёт объект.
- `to=$link.<field>` → разрешены только address, method, password, port, remark.
  Другие цели игнорируются. scheme изменять нельзя.

Оба прохода используют общий mapper из [common.md](common.md). Источники copy — resolved
host либо rawInbound, не промежуточный ShareLink. Поэтому разделение двух последовательностей
не создаёт межполевых зависимостей copy. Query можно перезаписать или удалить.

После mapper `sanitizeLink()`:

| Поле | Правило |
| --- | --- |
| scheme | Всегда исходный scheme |
| address | String(value ?? '').trim(), пустое → исходное |
| port | Number(value), integer 1..65535, иначе исходный |
| password | String(value ?? ''), пустое → исходное |
| method | undefined остаётся undefined, иначе String(value); пустое → исходное |
| remark | null/undefined → исходное; иначе String, пустая строка допустима |

Пример операции, меняющей адрес: `{"op":"set","to":"$link.address","value":"vpn.example.org"}`.
Пример query key с точками: `{"op":"set","to":"extra.custom","value":true}` →
буквальный `extra.custom=true`, а не JSON-object. Ошибочный $link.port не удаляет исходный порт.

## Escaping и Python

`formatAddress`: содержит `:` и не начинается с `[` → заключить в квадратные скобки.
Это эвристика, а не полноценный IP parser; уже bracketed IPv6 остаётся.
Адрес не percent-encoded. Remark и password VLESS/Trojan/Hysteria2 — encodeURIComponent.
Query: Object.entries по порядку, undefined/null исключить, остальные → JS String(value),
затем encodeURIComponent для ключа и значения, соединить `&`.

Предлагаемый совместимый примитив:

```python
from urllib.parse import quote

def encode_uri_component(text: str) -> str:
    return quote(text, safe="~!*'()-._", encoding="utf-8", errors="strict")
```

Нельзя использовать quote_plus/urlencode по умолчанию: пробел должен стать `%20`,
а не `+`. JS String(bool) — `true`/`false`, str(bool) — несовместимо. Сложные значения
mapper в query автоматически не JSON-кодируются: object → `[object Object]`, array
→ comma-joined string. Only extra/fm кодируются JSON самим генератором.
JS integer-like query keys имеют особый порядок enumeration; при byte parity учесть это.
Для одиноких UTF-16 surrogate encodeURIComponent бросает ошибку; не заменять их молча.

## Extended clients

Если isExtendedClient=true и description truthy, после уже полного URI добавляется:

```ts
links.push(`${link}?serverDescription=${host.clientOverrides.serverDescription}`);
```

Следовательно suffix находится **после `#remark`**, внутри fragment с точки зрения URL parser.
Description уже обычный Base64 из resolver, без дополнительного escaping; его нельзя
переносить в query перед `#` при совместимом порте. Plain info API передаёт extended=false.

## Пример

Для resolved host: finalRemark=`Demo`, address=`vpn.example.com`, port=443,
protocol=vless/id=`11111111-1111-4111-8111-111111111111`, encryption=none, flow='',
transport=ws/path=`/ws?ed=2048`/host=`cdn.example.com`, heartbeatPeriod=null,
security=tls/serverName=`cdn.example.com`/fingerprint=chrome/alpn=`h2,http/1.1`,
остальные TLS поля null, finalMask=null и mapper={}:

```text
vless://11111111-1111-4111-8111-111111111111@vpn.example.com:443?encryption=none&type=ws&path=%2Fws%3Fed%3D2048&host=cdn.example.com&security=tls&sni=cdn.example.com&fp=chrome&alpn=h2%2Chttp%2F1.1#Demo
```

Пример показывает plaintext до внешнего Base64. Наличие newline в code fence не означает
завершающий LF в фактической строке.

## Проверочные сценарии переноса

1. Все четыре URI-схемы; SS2022 составной пароль; Unicode remark/password.
2. IPv4, домен, bare IPv6 и bracketed IPv6; пробелы, `+`, `&`, `/`, `#`, `=` в компонентах.
3. Пустой SNI сохраняет `sni=`; null исключается; encryption/flow порядок и omission.
4. TCP HTTP массивы, gRPC gun/multi, WS heartbeat=0, XHTTP extra и KCP congestion loss.
5. TLS pcs/vcn/cs; Reality pbk/sid/pqv/spx; отсутствующий публичный ключ.
6. Hysteria2 с первым salamander без пароля и вторым с паролем; fm и pinSHA256.
7. Mapper set/copy/unset query; literal dot key; каждый разрешённый $link target;
   port='443', port=0, >65535, non-integer; empty/null remark.
8. SS query mapper не попадает в URI; extended suffix после fragment.
9. Два URI → один LF, без trailing LF; пустой результат; UTF-8/Base64 round trip.
10. isHidden напрямую не фильтруется; format exclusion; ошибка generateLinks против generateConfig.
