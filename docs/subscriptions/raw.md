# RAW, browser/info и connection keys API

Источник: Remnawave backend **3.4.5**, коммит `010b365ab1fabea01192b5e6ade4e98e66ee1dbd`.
Контракт resolver: [common.md](common.md). Генерация URI: [xray-base64.md](xray-base64.md).
RAW — промежуточный формат панели, не конфиг, который можно напрямую передать Xray/sing-box.

## Исходники

- [subscription.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/subscription.service.ts): getRawSubscriptionByShortUuid (строки 304–447), getSubscriptionInfo/getUserInfo (449–564), getConnectionKeysByUserId (конец файла).
- [render-templates.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/render-templates.service.ts#L109-L121): generateRawSubscription.
- [raw-subscription.response.model.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/models/raw-subscription.response.model.ts): RawSubscriptionWithHostsResponse.
- [subscription-raw.response.model.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/models/subscription-raw.response.model.ts): SubscriptionRawResponse для info/browser.
- [get-raw-subscription-by-short-uuid.command.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/commands/subscriptions/get-by/get-raw-subscription-by-short-uuid.command.ts): query/response schema.
- [subscriptions.controller.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/controllers/subscriptions.controller.ts): API envelope.

Не путать классы с похожими названиями: `RawSubscriptionWithHostsResponse` содержит
resolvedProxyConfigs, `SubscriptionRawResponse` содержит links и пользовательскую сводку.

## RAW pipeline

1. Загрузить user по shortUuid, запросив activeInternalSquads=true.
2. Загрузить subscription settings; отсутствие user/settings возвращает соответствующий fail.
3. Применить external squad overrides.
4. Сформировать user profile headers.
5. Если включён HWID — проверить device limit и поправить headers; иначе асинхронно
   зарегистрировать/обновить устройство.
6. Если подписка разрешена, запросить hosts с withDisabledHosts и **hidden=true**.
7. При randomizeHosts перемешать hosts, вызвать generateRawSubscription.
8. При HWID-denied и isShowCustomRemarks=true и maxDeviceReached/hwidNotSupported
   вызвать resolver с hosts=[] и соответствующими fallback flags.
9. При другом HWID-denied оставить subscription undefined → resolvedProxyConfigs=[].
10. Асинхронно зарегистрировать запрос как matchedRuleName=RAW, matchedResponseType=RAW.
11. Вернуть envelope с user, convertedUserInfo, headers и resolvedProxyConfigs.

Query withDisabledHosts: исходная Zod-схема принимает строку, true только при точном
`'true'`; отсутствие → `'false'` → false. `'TRUE'`, `'1'` не дают true.
Raw API не делает format exclusions: у каждого entry сохраняется metadata.excludeFromSubscriptionTypes,
но запись не исключается по XRAY_JSON/MIHOMO/... после resolver.

```ts
return await this.resolveProxyConfigService.resolveProxyConfig({
    subscriptionSettings,
    hosts,
    user,
    hostsOverrides,
    fallbackOptions,
});
```

generateRawSubscription не вызывает генераторы, не загружает клиентский шаблон и
не применяет host mapper к готовому outbound. Mapper сохраняется в clientOverrides,
чтобы его мог применить следующий слой.
Этот wrapper не передаёт excludeHostsByTags в resolver: произвольный SRR tag filter
не следует автоматически добавлять в RAW-контракт.

## Полный response envelope

Контроллер возвращает `{"response": <RawSubscriptionWithHostsResponse>}`.

| Поле response | Содержимое |
| --- | --- |
| user | GetFullUserResponseModel / ExtendedUsersSchema, полная пользовательская модель API |
| convertedUserInfo.daysLeft | dayjs(expireAt).diff(now,'day'), без max(0) в отличие от template DAYS_LEFT |
| convertedUserInfo.trafficUsed | prettyBytesUtil(usedTrafficBytes) с default options |
| convertedUserInfo.trafficLimit | prettyBytesUtil(trafficLimitBytes) |
| convertedUserInfo.lifetimeTrafficUsed | prettyBytesUtil(lifetimeUsedTrafficBytes) |
| convertedUserInfo.hwidCheckup | null либо subscriptionAllowed, maxDeviceReached, hwidNotSupported, limitBypassed |
| headers | Dictionary рассчитанных profile/HWID headers; это данные JSON, не сами автоматически отправленные profile headers |
| resolvedProxyConfigs | Полный массив intermediate entries |

Служебный endpoint path в constants:
`subscriptions/by-short-uuid/<shortUuid>/raw` (API prefix определяется приложением).
Не выводить из этого относительного пути предположение об authentication bypass;
авторизация остаётся ответственностью transport/API слоя.

## Структура одного resolved entry

JSON ниже — только entry, не полный API envelope; все значения вымышленные.

```json
{
  "finalRemark": "Demo",
  "address": "vpn.example.com",
  "port": 443,
  "streamOverrides": {"finalMask": null, "sockopt": null},
  "mux": null,
  "clientOverrides": {
    "shuffleHost": false,
    "mihomoX25519": false,
    "mihomoIpVersion": null,
    "serverDescription": null,
    "xrayJsonTemplate": null,
    "mapper": {}
  },
  "metadata": {
    "uuid": "11111111-1111-4111-8111-111111111111",
    "tags": [],
    "excludeFromSubscriptionTypes": [],
    "inboundTag": "VLESS",
    "configProfileUuid": null,
    "configProfileInboundUuid": null,
    "isDisabled": false,
    "isHidden": false,
    "viewPosition": 0,
    "remark": "Demo",
    "vlessRouteId": null,
    "rawInbound": {"tag": "VLESS", "protocol": "vless", "settings": {}}
  },
  "protocol": "vless",
  "protocolOptions": {
    "id": "11111111-1111-4111-8111-111111111111",
    "encryption": "none",
    "flow": ""
  },
  "security": "none",
  "transport": "tcp",
  "transportOptions": {"header": null}
}
```

securityOptions отсутствует при none. При TLS/Reality он соответствует union из
[common.md](common.md). Null fields нужно сохранять; их нельзя автоматически исключать
через exclude_none=True. metadata.rawInbound хранит исходный серверный JSON целиком,
включая его серверные settings, а не только клиентские поля. Поэтому RAW API и
публичные конфиги имеют разные контракты раскрываемых данных.

## Browser/info API

`getSubscriptionInfo()` выбирает user по username/id/shortUuid либо использует переданный
userEntity. Settings берёт по приоритету overrides.subscriptionSettings →
subscriptionSettingsRaw → cached settings. External squad применяется, если есть squad
и не передан overrides. При отсутствии settings — fail, а не пустая подписка.

Если HWID выключен **или authenticated=true**, получает hosts с disabled=false,
hidden=false, вызывает resolver и `generateLinks(formattedHosts, false)`.
Если HWID включён и authenticated=false, links остаётся []; здесь не выполняется
проверка HWID headers с возможностью открыть ссылки. randomizeHosts service-флаг
в этой ветке не применяется, но resolver.shuffleHost работает.

Результат SubscriptionRawResponse:

| Поле | Значение |
| --- | --- |
| isFound | true |
| user.shortUuid, username | Из пользователя |
| user.daysLeft | Целые дни, могут быть отрицательными |
| user.trafficUsed, trafficLimit, lifetimeTrafficUsed | prettyBytesUtil с default options |
| user.trafficUsedBytes, trafficLimitBytes, lifetimeTrafficUsedBytes | Строки bigint |
| user.expiresAt | Дата; в JSON ISO datetime |
| user.isActive | status===ACTIVE |
| user.userStatus, trafficLimitStrategy | Исходные enum |
| links | Массив plaintext share links, без extended description |
| ssConfLinks | В этой версии создаётся пустой object `{}` и не заполняется |
| subscriptionUrl | URL подписки пользователя |

ssConfLinks не означает существование отдельного Outline/SS JSON генератора в этом
pipeline. Не добавлять такой формат на основании одного имени response field.

Для публичного subscription response type=BROWSER service сразу возвращает этот info
object. Controller отправляет его JSON-ответом HTTP 200 напрямую, минуя
finalizeSubscriptionResponse: age encryption и profile/response-rule headers из обычной
ветки здесь не применяются. Таблица response types содержит text/html, но это не
фактическая сериализация этой ветки. Info endpoint/административные методы могут
добавлять внешний `response` envelope; публичный BROWSER response отправляется напрямую.

## Connection keys по категориям

`getConnectionKeysByUserId()` запрашивает all hosts с disabled=true, hidden=true,
затем независимо выделяет:

| Массив | Условие |
| --- | --- |
| enabledKeys | !isDisabled && !isHidden |
| disabledKeys | isDisabled && !isHidden |
| hiddenKeys | isHidden && !isDisabled |

Host с обоими flags=true не входит ни в один массив. Для enabled запускается resolver
даже при [] (возможен empty-host fallback); для disabled/hidden при [] возвращается []
без resolver. Каждая категория имеет отдельную обработку remarks/dedup/shuffle и
затем generateLinks(..., false); exclusion XRAY_BASE64 действует для всех.
Общий randomizeHosts flag отдельно не применяется. Output содержит три массива URI,
не Base64 blob и не ResolvedProxyConfig objects.

## Python-перенос и проверки

Использовать тот же Python resolver, что и клиентские форматы, без дополнительного
построения outbounds. Держать отдельные DTO для RAW и info/browser. Числа bigint вне
resolved-модели сериализуются по соответствующему API-контракту; не полагаться на
случайные coercions сериализатора. Полная user-модель — отдельный API contract и не
обязательна генераторам, которым нужны только credentials и template variables.

Проверить:

1. withDisabledHosts exact string conversion, hidden=true, absent inbound skip.
2. Format exclusions сохранены как metadata и не исключают raw entry.
3. mapper сохранён, но не выполнен; client template сохранён, но не rendered.
4. HWID allowed/denied/fallback branches, headers в JSON envelope.
5. daysLeft отрицательный в info/raw, но clamp в template variable.
6. securityOptions missing vs null, bigint strings и ISO dates.
7. Info HWID enabled unauthenticated → пустые links, ssConfLinks всегда {}.
8. BROWSER direct JSON против обычной генерации/encryption; разные envelopes.
9. Connection keys flags, dual-disabled-hidden omission, empty enabled fallback,
   независимые dedup и exclusions XRAY_BASE64.
