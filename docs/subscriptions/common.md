# Общий pipeline и контракт переноса на Python

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Навигация и матрица форматов: [README.md](README.md).

## 1. Карта исходников

Все пути ниже относятся к внешнему репозиторию `remnawave/backend`.

| Файл | Ответственность |
| --- | --- |
| [config-profile.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/config-profiles/config-profile.service.ts#L145-L170) | `XRayConfig.getAllInbounds()` → сохранение `rawInbound` |
| [hosts.repository.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/hosts/repositories/hosts.repository.ts#L169-L255) | Выбор доступных hosts и загрузка инбаундов/шаблонов |
| [get-hosts-for-user.handler.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/hosts/queries/get-hosts-for-user/get-hosts-for-user.handler.ts) | Соединение host с `rawInbound` и шаблоном |
| [resolve-proxy-config.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/resolve-proxy/resolve-proxy-config.service.ts) | Вся нормализация, fallback, transport/security/protocol |
| [resolved-proxy-config.interface.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/resolve-proxy/interfaces/resolved-proxy-config.interface.ts) | TypeScript-контракт результата |
| [resolved-proxy-config.schema.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/models/resolved-proxy-config.schema.ts) | Zod-контракт raw API |
| [apply-host-mapper.util.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/host-mapper/apply-host-mapper.util.ts) | Последовательные преобразования выходных полей |
| [subscription-template.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/subscription-template.service.ts#L299-L356) | Загрузка и кеширование клиентских шаблонов |

## 2. Доступность и порядок хостов

`findActiveHostsByUserId(userId, returnDisabledHosts=false, returnHiddenHosts=false)`:

1. Выбирает `hosts`, для которых существует связь инбаунда с internal squad пользователя.
2. Учитывает `internalSquadHostLinks`: наличие связи сравнивается с
   `hosts.internalSquadsMode == ALLOW_ONLY`. Для ALLOW_ONLY связь обязательна;
   для другой ветки наличие связи исключает хост в рамках проверяемого squad.
   Используется `EXISTS`: достаточно хотя бы одного подходящего squad, без дублирования host.
3. При false-флагах исключает `isDisabled` и `isHidden` соответственно.
4. Сортирует по `viewPosition ASC`; дополнительного tie-breaker нет.

Handler собирает уникальные UUID инбаундов и Xray JSON templates, загружает их через
raw cache, создаёт `HostWithRawInbound`. Хост без найденного инбаунда пропускается.
Отсутствующий host template превращается в `null`.

Публичная подписка запрашивает disabled=false, hidden=true только для `XRAY_JSON` и
`MIHOMO`. Raw API запрашивает hidden=true и настраиваемый disabled. Info API — оба false.
Генератор, вызванный напрямую, не должен неявно повторять фильтры SQL.

Если `subscriptionSettings.randomizeHosts`, service предварительно перемешивает весь
массив. Затем resolver при наличии `shuffleHost=true` переносит все такие хосты в начало
и перемешивает их; остальные сохраняют относительный порядок.

## 3. Порядок работы resolver

`resolveProxyConfig(options)` выполняет:

1. `subscriptionSettings === null` → `[]`.
2. Удаляет хосты, у которых хотя бы один tag входит в `excludeHostsByTags`.
3. Проверяет ранние remarks/fallback по уже отфильтрованному количеству хостов.
4. Применяет shuffle.
5. Вычисляет карты Reality X25519, ML-DSA и VLESS encryption из `rawInbound`.
6. Создаёт карту переменных пользователя для названий.
7. Для каждого хоста применяет external squad overrides, подстановки в remark и dedup.
8. Собирает protocol, transport, security, общие поля; неподдерживаемый protocol пропускает.

В обычном цикле ошибки одного хоста здесь не перехватываются. Ошибка может прервать
resolver; внешние service-методы затем переводят её в свой ошибочный ответ.
Исходный resolver мутирует `options.hosts` при tag-фильтрации и сами host-объекты при overrides.
В Python допустимо изолировать объекты запросов копированием, сохранив результат.

Основная конструкция:

```ts
const protocol = this.resolveProtocolOptions(
    inputHost, inbound, user, ctx.encryptionMap.get(inputHost.inboundTag),
);
if (!protocol) return null;
const transport = this.resolveTransport(inbound.streamSettings, inputHost, protocol, {
    vlessUuid: user.vlessUuid,
});
const security = this.resolveSecurity(
    inbound.streamSettings, inputHost, inbound.tag!,
    ctx.publicKeyMap, ctx.mldsa65PublicKeyMap, address,
);
```

## 4. Промежуточная модель

`ResolvedProxyConfig` — общие поля плюс три независимых tagged unions:
`protocol/protocolOptions`, `transport/transportOptions`, `security/securityOptions`.
При `security=none` свойства `securityOptions` **нет**, это не `null`.

| Поле | Построение |
| --- | --- |
| `finalRemark` | Подстановка переменных в host.remark, затем dedup |
| `address` | `resolveRandomizedValue(host.address)` |
| `port` | Только `host.port` |
| `streamOverrides.finalMask` | Непустой host.finalMask, иначе непустой inbound.streamSettings.finalmask, иначе null |
| `streamOverrides.sockopt` | Только непустой host.sockoptParams, иначе null |
| `mux` | Только непустой host.muxParams, иначе null |
| `clientOverrides.shuffleHost` | host.shuffleHost |
| `clientOverrides.mihomoX25519` | host.mihomoX25519 |
| `clientOverrides.mihomoIpVersion` | host.mihomoIpVersion |
| `clientOverrides.serverDescription` | UTF-8 → обычный Base64, если описание truthy, иначе null |
| `clientOverrides.xrayJsonTemplate` | Загруженный шаблон конкретного хоста или null |
| `clientOverrides.mapper` | host.mapper |
| `metadata` | uuid, tags, excludeFromSubscriptionTypes, inboundTag, configProfileUuid, configProfileInboundUuid, isDisabled, isHidden, viewPosition, исходный remark, vlessRouteId, rawInbound |

`toNonEmptyRecord()` проверяет null и `Object.keys(value).length`, но не доказывает,
что значение — plain dictionary. Не следует приравнивать любой пустой Python-контейнер
к исходной проверке без учёта формы данных.

## 5. Приоритеты и protocol

```ts
return (hostValue || inboundValue) ?? null;
```

Это полный алгоритм `override()`. Falsy host уступает inbound; при этом falsy inbound
(`''`, `false`, `0`) сохраняется, если не null/undefined. Непустой или пустой JS-объект truthy.
Host path/host/fingerprint нельзя переносить через простое «если не None».

Для любого протокола отсутствие truthy `inbound.settings` → хост пропускается.
Пустой JS-объект settings `{}` допускается.

| Protocol | Результат protocolOptions |
| --- | --- |
| `vless` | `id=route_uuid(user.vlessUuid, host.vlessRouteId)`, `encryption=map[tag] ?? 'none'`, `flow=getVlessFlow(inbound)` |
| `trojan` | `password=user.trojanPassword` |
| `shadowsocks` | method=`settings.method || 'chacha20-ietf-poly1305'`, password см. ниже, uot=`settings.uot || false`, uotVersion=`settings.uotVersion || 1` |
| `hysteria` | `version=2` |
| Другие, включая VMess | `null`, хост пропускается |

SS2022 распознаётся только для точного метода `2022-blake3-aes-256-gcm`. Если в settings
есть ключ `password`, итог: `settings.password + ':' + base64_utf8(user.ssPassword)`.
Проверяется наличие ключа, а не его truthiness. Другие SS2022-методы автоматически не распознаются.
В остальных случаях используется user.ssPassword без перекодирования.

`setVlessRouteForUuid()` при ненулевом числовом routeId заменяет символы UUID с индексами
14..17 на четыре hex-цифры нижних 16 бит routeId:
`uuid[:14] + f'{route_id & 0xffff:04x}' + uuid[18:]`.
0/null/undefined оставляют UUID без изменений. Например, routeId=4660:
`11111111-1111-4111-8111-111111111111` → `11111111-1111-1234-8111-111111111111`.
Заменяется вся третья группа, включая исходный version nibble UUID; дефисы сохраняются.

`getVlessFlow()` сначала учитывает `inbound.settings.flow`: только точное
`xtls-rprx-vision` сохраняется, любое другое явно заданное значение даёт `''`.
Если flow отсутствует, TLS/Reality + raw/tcp дают vision, остальное `''`.
Flow определяется по исходному инбаунду **до** host.securityLayer override.

Источники: [ss-cipher.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/helpers/xray-config/ss-cipher.ts),
[get-vless-flow.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/flow/get-vless-flow.ts),
[set-vless-route-for-uuid.util.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/vless-route/set-vless-route-for-uuid.util.ts).

## 6. Transport

Отсутствующий streamSettings/network и неизвестный network → tcp с header=null.
`raw` нормализуется в `tcp`, но читает `rawSettings`, а не `tcpSettings`.

| Транспорт | Поля transportOptions |
| --- | --- |
| `ws` | path=override(host.path, wsSettings.path); host=randomize(override(host.host, wsSettings.host) ?? ''); headers=wsSettings.headers ?? null; heartbeatPeriod=wsSettings.heartbeatPeriod ?? null |
| `httpupgrade` | path/host аналогично WS; headers=httpupgradeSettings.headers ?? null |
| `grpc` | authority=randomize(override(host.host, grpcSettings.authority) ?? ''); serviceName=override(host.path, grpcSettings.serviceName); multiMode=!!grpcSettings.multiMode |
| `xhttp` | path/host аналогично WS; mode=xhttpSettings.mode ?? 'auto'; extra=override(toNonEmptyRecord(host.xhttpExtraParams), xhttpSettings.extra) |
| `kcp` | clientMtu=clientMtu || mtu || 1350; clientTti=clientTti || tti || 50; congestion=congestion || false |
| `hysteria` | version=2; для protocol=hysteria auth=route_uuid(user.vlessUuid, routeId), иначе settings.auth при truthy, иначе `''` |

TCP HTTP camouflage имеет особую ветку. При `header.type=http` клонируется только
`header.request`, затем собирается новый header `{type:'http', request}`; response теряется.
Если request отсутствует, создаётся GET/1.1 с Accept-Encoding=[gzip,deflate],
Connection=[keep-alive], Pragma=[no-cache]. В этой ветке host.host/path **не применяются**.
Если request был задан (даже `{}`), его headers дополняются и truthy host.host/path
заменяют Host/path одноэлементными массивами. Для остальных header он сохраняется целиком.

XHTTP `extra` заменяется целиком, без deep merge. Host/authority рандомизируются;
path/serviceName не рандомизируются и пользовательские переменные в них не подставляются.

## 7. Security и SNI

Без streamSettings немедленно возвращается `{security:'none'}`, даже если host требует TLS.
Иначе исходный `streamSettings.security` можно переопределить host.securityLayer:
`TLS` → tls, `NONE` → none, `DEFAULT` → исходное значение. Отдельного Reality override нет.
Неизвестное/отсутствующее security → none.

TLS securityOptions:

| Поле | Источник |
| --- | --- |
| `alpn` | override(host.alpn, tls.alpn как comma-строка) ?? `''` |
| `fingerprint` | override(host.fingerprint, tls.fingerprint) ?? chrome |
| `serverName` | Отдельный SNI resolver |
| `enableSessionResumption` | `!!tls.enableSessionResumption` |
| `echConfigList`, `echForceQuery`, `cipherSuites` | Соответствующее tls поле `|| null` |
| `echSockopt` | Непустой tls.echSockopt или null |
| `pinnedPeerCertSha256`, `verifyPeerCertByName` | Только host, без fallback на tlsSettings |

Reality: fingerprint через override/default chrome; publicKey из карты по inbound.tag
или `''`; shortId — **первый** shortIds или `''`; serverName через SNI resolver с
первым serverNames; spiderX=`reality.spiderX || ''`; mldsa65Verify из карты или null.
serverNames/shortIds не выбираются случайно.

SNI, строго по приоритету:

1. keepSniBlank → `''`.
2. overrideSniFromAddress → уже рандомизированный address.
3. Truthy host.sni заменяет предложенный инбаундом serverName.
4. При пустом SNI и доменном **исходном** host.address используется host.address.
5. Полученный SNI отдельно рандомизируется.

Домен проверяется ASCII regex с несколькими labels и буквенным TLD длиной ≥2.
IP, wildcard, список адресов через запятую, localhost и Unicode IDN без punycode не подходят.
Рандомизированные address и SNI могут различаться, если они вычислялись отдельно.
Исходный tlsSettings.allowInsecure resolver не читает: многие форматы включают insecure
по наличию **host.pinnedPeerCertSha256**. Это фактическое поведение, не рекомендация для дизайна.

## 8. Криптографические преобразования

Источник: [resolve-public-key.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/helpers/xray-config/resolve-public-key.ts),
[generate-encryption-from-decryption.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/helpers/vless-encryption/generate-encryption-from-decryption.ts).

Карты индексируются tag, а кеши — исходным privateKey/seed/decryption. Первый успешно
вычисленный результат для tag выигрывает; повторные tag с другими ключами могут использовать
чужой первый результат. Ошибки отдельного ключа перехватываются, соответствующей записи нет.

- Reality X25519: base64/base64url private key → raw bytes → JWK OKP/X25519 private key →
  public JWK `x`. Результат — Base64URL без padding. Для Python нужен X25519 public derivation,
  например соответствующий примитив криптобиблиотеки; не копирование private key.
- Reality ML-DSA-65: `realitySettings.mldsa65Seed` → `ml_dsa65.keygen(seed).publicKey` →
  Base64URL без padding. Совместимость seed/keygen должна проверяться по точным тест-векторам.
- VLESS: только protocol=vless и непустое decryption != none. Разбор строки
  `mlkem768x25519plus.<native|xorpub|random>.<ticketLifetime>.<padding...>.<keys...>`.
  ticketLifetime обязателен, но как duration не проверяется. До первого декодированного
  32/64-байтового ключа части считаются padding и соединяются точками. После первого ключа
  непустая часть другой длины — ошибка. Пустые части после начала ключей пропускаются.
  Ключей должен быть хотя бы один.
- 32 байта → X25519 private key; 64 байта → ML-KEM-768 seed, **не готовый secret key**.
  Вычислить public keys в исходном порядке. Encryption:
  `protocol.mode.<1rtt если ticketLifetime == '0s', иначе 0rtt>[.padding].publicKeys...`.
  Ошибка любого ключа приводит к отсутствию encryption для инбаунда и default `none`.

Node Buffer декодирует Base64 достаточно терпимо и принимает URL-алфавит. Строгий Python
decoder без нормализации padding может менять поведение. Для PQC нельзя подменять ML-DSA-65
или ML-KEM-768 похожей схемой: версию/алгоритм и seed API сверить отдельно при реализации.

## 9. Названия, переменные, случайность

Источники: [template-parser.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/templates/template-parser.ts),
[replace-templates-values.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/templates/replace-templates-values.ts),
[get-next-traffic-reset-at.util.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/get-next-traffic-reset-at.util.ts),
[pretty-bytes.util.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/bytes/pretty-bytes.util.ts).

Синтаксис: `{{KEY}}` или `{{KEY:k=value|k2=value2}}`; regex
`\{\{(\w+)(?::([^{}]*))?\}\}`. Ключи регистрозависимы. Неизвестные placeholders остаются.
Argument разбивается по первому `=`, имя trim, значение сохраняет пробелы; повторный ключ
заменяет предыдущий. Парсер принимает аргументы независимо от перечисленных схемой.
Префикс `rwEncodeBase64:` кодирует весь результат после подстановки и возвращает `base64:<data>`.
Парсинг кешируется на 10 000 записей с вытеснением самой старой записи, не полноценный LRU.

| Переменные | Значение |
| --- | --- |
| DAYS_LEFT | max(0, целые дни expireAt-now по dayjs) |
| TRAFFIC_USED, TRAFFIC_LEFT, TOTAL_TRAFFIC | prettyBytesUtil(..., sticky=true, prefixIndex=3), IEC; результат `String(res.size)`, не произвольный humanize |
| TRAFFIC_USED_BYTES, TRAFFIC_LEFT_BYTES, TOTAL_TRAFFIC_BYTES | Десятичные строки bigint; left=0 при unlimited=0, иначе limit-used без clamp |
| STATUS | args[user.status], иначе Active/Disabled/Expired/Limited и прочая капитализация enum |
| RESET_STRATEGY | args[user.trafficLimitStrategy], иначе сама стратегия |
| USERNAME, EMAIL, TELEGRAM_ID, TAG, DESCRIPTION | Пользовательские поля; nullable дают `''` |
| ID, SHORT_UUID | Строковый id и shortUuid |
| SUBSCRIPTION_URL | `https://<SUB_PUBLIC_DOMAIN>/<shortUuid>` |
| EXPIRE_UNIX, CREATED_AT_UNIX | Unix seconds соответствующей даты |
| LIFETIME_USED_BYTES | Десятичная строка lifetimeUsedTrafficBytes |
| LAST_TRAFFIC_RESET_AT_UNIX | Unix seconds или 0 |
| LAST_TRAFFIC_RESET_AT | Формат даты, args.format или DD.MM.YYYY; отсутствует → `''` |
| NEXT_TRAFFIC_RESET_AT_UNIX, NEXT_TRAFFIC_RESET_AT | Следующий reset; нет reset → 0 / `''` |
| SS_HWID_LIMIT | user.hwidDeviceLimit если не null, иначе fallbackDeviceLimit ?? 0; строка |

Вычисление next reset использует время/таймзону процесса dayjs: DAY — начало дня +5 минут;
WEEK — следующий понедельник +15 минут; MONTH — первое число +20 минут; MONTH_ROLLING —
день создания с clamp по длине месяца +10 минут, не раньше первого такого reset в следующем
после создания месяце. При совпадении с now выбирается следующий период. NO_RESET → null.
Числа bigint для prettyBytes приводятся к JS Number: возможна потеря точности больших значений.

Dedup работает по полностью подставленному remark: первый `A`, затем `A ^~2~^`,
`A ^~3~^`. Если исходное название содержит `^~` и заканчивается `~^`, номер первого повтора 1.
Глобальной проверки столкновений с уже существующими суффиксами нет. Dedup происходит
до format-фильтров; пропущенный позже хост всё равно занимает номер.

`resolveRandomizedValue()`:

1. Falsy строка возвращается как есть.
2. Есть запятая → случайный элемент `split(',')`, затем trim; wildcard в нём не раскрывается.
3. Иначе есть `*` → заменяется только **первое** вхождение токеном длиной 10 из
   `0123456789abcdefghjkmnopqrstuvwxyz`, затем trim.
4. Иначе строка возвращается без trim.

## 10. Fallback-конфигурации

При isShowCustomRemarks=true порядок раннего возврата:
HWID max devices → HWID unsupported → непустой respondWithRemarks → non-ACTIVE user.
Для EXPIRED/DISABLED/LIMITED выбираются соответствующие customRemarks; неизвестный
неактивный статус даёт `[]`. При isShowCustomRemarks=false эти ветки игнорируются.
После них hostCount=0 всегда использует customRemarks.emptyHosts, независимо от флага.
Неподдерживаемые протоколы/format-фильтры, опустошившие список позднее, fallback не запускают.

Remarks сначала проходят TemplateEngine. Каждый remark может содержать готовый JSON
ResolvedProxyConfig: после trim строка должна начинаться **точно** с `{"f`, распарситься
в non-array object. Runtime-schema проверки здесь нет; имя первого JSON-ключа влияет на выбор ветки.
Иначе создаётся dummy VLESS: address=0.0.0.0, port=1, zero UUID, encryption=none,
flow='', tcp/header=null, security=none, mux=null, stream overrides=null,
clientOverrides с false/null и mapper={}, metadata с zero UUID, пустыми tags/exclusions,
null profile UUID/rawInbound/vlessRouteId и исходным remark.
Fallback не проходит обычные shuffle/dedup/key derivation. Clash исключит dummy VLESS.

## 11. Host mapper

Секции: xrayJson, mihomo, singbox, base64; каждая — упорядоченный массив операций.
Clash mapper не применяет, Stash использует mihomo. Mapper выполняется после стандартной
сборки одного outbound/proxy/link, до сборки полного шаблона.

- `copy`: `from` без `$host.` читается из metadata.rawInbound; с префиксом — из resolved host.
- Разрешённые `$host` корни: address, port, finalRemark, protocol, protocolOptions,
  transport, transportOptions, security, securityOptions, mux,
  streamOverrides.finalMask, streamOverrides.sockopt, clientOverrides.serverDescription,
  metadata.remark, metadata.tags, metadata.inboundTag. Потомки разрешены.
- Missing source пропускается, `null` копируется. Source всегда исходный host/inbound,
  а не target после предыдущих операций.
- `set`: записывает literal (API-схема допускает строки, числа, bool, arrays, objects;
  literal null в set не входит, но copy может принести null).
- `unset`: удаляет поле; пустые родители остаются. Удаление индекса массива через lodash
  оставляет hole, а не сдвигает массив; при JSON.stringify hole превращается в null.
- Target deep-clone до изменений. Значения copy/set тоже deep-clone. Ошибка операции
  подавляется; остальные выполняются.
- Путь использует lodash.toPath/get/set/unset: dot и bracket syntax, индексы массивов.
  Если промежуточный target уже является примитивом, операция пропускается. null/undefined
  не блокируют создание объекта. Дефисы в именах не являются разделителями.
- Для URI flatTargets=true: весь query key, включая точки, считается одним literal ключом.
  `$link.`-обработку и sanitization см. [xray-base64.md](xray-base64.md).
- Проверки соответствия поля схеме клиента нет. Последующие операции могут удалить tag,
  изменить сервер или добавить неподдерживаемый параметр.

Python-порт должен отдельно воспроизвести array/dictionary paths, missing sentinel и
защиту путей библиотеки; простого `dict.update()` недостаточно.

## 12. Клиентские шаблоны и HTTP-обвязка

Запрашивается (name, type), имя по умолчанию `Default`; если именованного шаблона нет,
repository ищет Default того же type. Отсутствие обоих → исключение. Кеш на 3600 секунд.
YAML загружается через js-yaml `CORE_SCHEMA.withTags(mergeTag)` с unlimited aliases/merge keys;
JSON используется как object из БД. Пустой JS object допустим, отсутствие outbounds может
сломать конкретную render-ветку. Запись YAML в API передаётся как encodedTemplateYaml
Base64, затем декодируется в UTF-8. Это отличается от Base64 самой подписки.

Default templates задают DNS, локальные inbounds, routing/groups; генераторы не строят
эти секции по серверным инбаундам. У Xray default SOCKS 127.0.0.1:10808, HTTP :10809,
direct/freedom и block/blackhole; у sing-box tun и mixed :2412, selector и direct;
у Clash/Mihomo mixed :7890, socks :7891, redir :7892 и группа → Remnawave.
Default Stash описан отдельно в [stash.md](stash.md). Эти значения — исходные defaults,
не обязательные настройки порта: пользовательский шаблон имеет приоритет.

External squad settings применяются до генерации: subscriptionSettings через shallow merge,
customRemarks и hwidSettings заменяются целиком, headers add/remove обрабатываются отдельно.
Host overrides в resolver меняют только vlessRouteId и serverDescription; null тоже override,
потому что проверяется `!== undefined`. Именованный шаблон из response rules выигрывает;
при его отсутствии external squad может выбрать имя. Для первоначального XRAY_BASE64
поиск squad-шаблона производится как для XRAY_JSON, на случай последующего JSON fallback.

`serveJsonAtBaseSubscription` может переключить XRAY_BASE64 на XRAY_JSON для подходящего
User-Agent, если ignore-флаг не установлен. Extended clients определяются case-sensitive
regex: FlClash X/ (пробел необязателен), Flowvy/, prizrak-box/, koala-clash/, Happ/, INCY/.
Middleware дополнительно проверяет regex из matched rule
`responseModifications.additionalExtendedClientsRegex`; первое совпадение тоже включает
extended mode. Эти regex компилируются через JS RegExp и кешируются.
Stash вызывается с extended=false даже при подходящем User-Agent.

Заголовки профиля строятся независимо от body:

| Header | Базовое значение |
| --- | --- |
| content-disposition | attachment; filename=<username>, без дополнительного quoting |
| subscription-userinfo | upload=0; download=<Number(usedTrafficBytes)>; total=<Number(limit)>; expire=<Unix seconds либо 0 при expireAt.getFullYear()==2099> |
| subscription-refill-date | Unix seconds следующего traffic reset; отсутствует при NO_RESET |
| x-hwid-active | true при переданном hwidLimit |

Затем settings.customResponseHeaders проходят TemplateEngine и могут заменить базовые
headers. HWID-denied ветки дополнительно задают announce, x-hwid-not-supported,
x-hwid-max-devices-reached, x-hwid-limit; порядок и конкретные значения определяет service.
Заголовки response rules могут устанавливаться middleware раньше либо перекрывать
результат controller в конце при applyHeadersToEnd=true. Преобразование bigint в Number
в subscription-userinfo отличается от точных decimal strings raw API.
Источник: [get-user-info.headers.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/utils/get-user-info.headers.ts).

После генерации публичный controller может age-зашифровать **весь сериализованный body**
методом age1/age1pq1, используя trimmed recipient key, и выдать armored ciphertext
с Content-Type text/plain. Это отдельный transport layer; шифрование случайное и не
подходит для byte-for-byte сравнения. Ошибка encryption service даёт пустую строку.
HTTP headers собираются отдельно, response-rule headers перекрывают result.headers.

Источники: [subscription.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/subscription.service.ts),
[extended-clients.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/constants/extended-clients.ts),
[encrypt-response-body.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/helpers/response-encryption/encrypt-response-body.ts).

## 13. Python-совместимость и приёмка

Предлагаемые независимые слои: `select_hosts`, `resolve_proxy_configs`,
`apply_host_mapper`, `load_template`, `render_<format>`, `finalize_http_response`.
Для union-моделей использовать dataclass/TypedDict/Pydantic с discriminator и отдельным
MISSING sentinel. Не добавлять runtime-валидацию в местах, где TS делает только cast,
без осознанного изменения контракта.

| JS-операция | Требование к Python |
| --- | --- |
| `||` | JS truthiness: `{}` и `[]` truthy; bool исключить из числовых проверок, где TS typeof number |
| `??` | Fallback только для null/undefined, не для 0/false/пустой строки |
| undefined в object JSON | Поле отсутствует; null остаётся null |
| JSON.stringify | Compact JSON, Unicode UTF-8; Python separators=(',', ':') и ensure_ascii=False как база, не полная гарантия JS number formatting |
| NaN/Infinity в JSON.stringify | Превращаются в null, а не Python JSON NaN/Infinity; normalizer нужен до сериализации |
| Object.entries | Обычные string keys по insertion order; integer-like keys JS упорядочивает отдельно |
| String(value) | true/false lowercase, arrays comma-joined, object → [object Object]; Python str отличается |
| parseInt | Принимает числовой префикс, в отличие от int('12x'); radix в отдельных местах различается |
| Number | Пустая строка/пробелы → 0; decimal/scientific/hex допустимы; bool/null имеют особые значения |
| RegExp | JS ECMAScript regex ≠ Python re; не объявлять полную совместимость без ограниченного синтаксиса или JS-движка |
| js-yaml dump | Структурная совместимость YAML отдельно от идентичности quoting, aliases, indentation |

Минимальные проверки resolver: null settings; tag exclusion до fallback; отсутствие
инбаунда; пустой settings object; неизвестный protocol/network; rawSettings/tcpSettings;
host port отличается от inbound port; каждое falsy значение override; SNI-флаги вместе;
CSV+wildcard; TCP HTTP с request/без request; дедуп до format-фильтров; fallback JSON
с разным порядком ключей; маршрутизированный UUID; SS2022; одинаковые tags разных
инбаундов; invalid private key; несколько VLESS keys и padding; PQC test vectors;
mapper copy missing/null, nested paths, array holes и запрет прохода через примитив.
