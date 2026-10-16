# Идентификация приложений и выбор формата подписки

Спецификация поведения `remnawave/backend` **3.4.5**, коммит
[`010b365ab1fabea01192b5e6ade4e98e66ee1dbd`](https://github.com/remnawave/backend/tree/010b365ab1fabea01192b5e6ade4e98e66ee1dbd).
Анализ выполнен 2026-10-17. Документ дополняет
[описание генераторов](subscriptions/README.md) и предназначен для переноса на Python.
Описывается поведение закреплённого исходника, а не установленный набор правил конкретного сервера.

## 1. Главный принцип

Remnawave не определяет ядро, платформу и возможности приложения автоматически.
Он выбирает **response type** по настраиваемым условиям HTTP-запроса, главным образом
`User-Agent` и `Accept`, либо по явному суффиксу URL. Первая подходящая rule выигрывает.
Отдельно вычисляются:

| Результат | Как определяется | На что влияет |
| --- | --- | --- |
| matchedResponseType | URL suffix или response rules | Выбор генератора / browser / блокировки |
| isExtendedClient | Встроенные regex + regex совпавшего правила | Дополнительное serverDescription в поддерживающих форматах |
| Возможность JSON fallback | Отдельный case-sensitive список UA + settings | Переключение XRAY_BASE64 → XRAY_JSON |
| Шаблон | Rule modifications, external squad, host template, Default | Содержимое выбранного формата |
| HWID | x-hwid и device headers + settings | Разрешение выдачи / fallback remarks, не выбор ядра |

Один признак не заменяет остальные. Например, `FlClash/1` получает MIHOMO, но не
extended description; `Happ/1` сначала получает XRAY_BASE64 и extended=true, а JSON
получает только при включённой настройке fallback или явном `/json`.
UA — заявленная строка запроса; совпадение не доказывает фактическую поддержку формата.

## 2. Карта исходников

Все ссылки закреплены за указанным коммитом внешнего репозитория.

| Исходник | Ответственность |
| --- | --- |
| [prisma/seed/default/response-rules.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/prisma/seed/default/response-rules.ts) | Полный default порядок правил и UA regex |
| [10_seed-response-rules.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/prisma/seed/seeders/10_seed-response-rules.ts) | Инициализация/обновление defaults в БД |
| [response-rules-matcher.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-response-rules/services/response-rules-matcher.service.ts) | matchRules, matchRule, matchCondition, applyOperator, handleOverrideClientType |
| [response-rules.middleware.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-response-rules/middleware/response-rules.middleware.ts) | Проверка запроса, построение SRR context, modifications, extended clients |
| [response-rules-parser.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-response-rules/services/response-rules-parser.service.ts) | Валидация конфигурации и regex |
| [extended-clients.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/constants/extended-clients.ts) | Отдельные списки extended и JSON fallback |
| [subscription.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/subscription.service.ts) | BROWSER, squad settings/templates, HWID, позднее переключение формата |
| [render-templates.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/render-templates.service.ts) | Response type → конкретный генератор |
| [subscription.module.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/subscription.module.ts) | Какие маршруты используют middleware |
| [request-template-type.constant.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/constants/subscription-template/template-type/request-template-type.constant.ts) | Допустимые ручные суффиксы |
| [truncate-header.util.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/common/utils/truncate-header.util.ts) | UA в context: первый элемент array, максимум 512 символов |

## 3. Откуда берутся действующие правила

Middleware получает `subscriptionSettings.responseRules` через cached settings query.
Default rules — начальные данные, не зашитый неизменяемый classifier:

- Если responseRules в БД null, seed записывает SRR_DEFAULT_CONFIG.
- Если hash существующих rules совпадает с hash предыдущего default, seed может
  заменить его новым default. Порядок массива участвует в hash.
- Пользовательские rules, не совпавшие с предыдущим default, автоматически не
  приравниваются к содержимому `prisma/seed/default/response-rules.ts`.
- При обновлении subscription settings parser проверяет schema/regex, затем кеш
  subscription settings инвалидируется.

Версия JSON-конфигурации rules — строка `"1"`. Rules — упорядоченный массив;
settings.disableSubscriptionAccessByPath optional. Rule содержит name, enabled,
operator=AND/OR, conditions, responseType и optional responseModifications.
Поле description необязательно; оно не влияет на сопоставление.

Источники схем: [response-rules-config.schema.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/models/response-rules/response-rules-config.schema.ts),
[response-rule.schema.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/models/response-rules/response-rule.schema.ts),
[subscription-settings.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-settings/subscription-settings.service.ts).

## 4. Маршруты и приоритет ручного выбора

Относительные пути controller, без предположения о reverse-proxy/API prefix:

| Путь | Поведение |
| --- | --- |
| `/sub/<shortUuid>` | Автоматический выбор по rules |
| `/sub/<shortUuid>/<clientType>` | Явный response type, если path access разрешён |
| `/sub/<shortUuid>/info` | Info API, исключён из response-rules middleware |

Допустимые clientType **регистрозависимы**:

| Суффикс | Response type | Документ формата |
| --- | --- | --- |
| json | XRAY_JSON | [xray-json.md](subscriptions/xray-json.md) |
| v2ray-json | XRAY_JSON, тот же генератор | [xray-json.md](subscriptions/xray-json.md) |
| mihomo | MIHOMO | [mihomo.md](subscriptions/mihomo.md) |
| clash | CLASH | [clash.md](subscriptions/clash.md) |
| stash | STASH | [stash.md](subscriptions/stash.md) |
| singbox | SINGBOX | [singbox.md](subscriptions/singbox.md) |

Суффиксов base64, xray-json, sing-box и browser в этом списке нет. Неизвестное truthy
clientType matcher переводит в BLOCK; при обычном прохождении middleware это 403
до controller validation. DTO также ограничивает clientType enum.

Если disableSubscriptionAccessByPath=true, любой truthy overrideClientType → BLOCK.
Это не отключает базовый URL. Если flag не установлен, ручной выбор выполняется
**до** перебора rules и возвращает matched=true, responseType, **без matchedRule**.

Следствия ручного выбора:

- `/json` имеет приоритет над Accept:text/html и UA-сигнатурой.
- Ни одна response rule и её modifications не применяются: нет rule-specific
  subscriptionTemplate, encryption, disableHwidCheck, исключённых tags, custom extended
  regex, response headers и respondWithRemarks.
- Встроенный extended detector всё равно работает. Общие user/squad/HWID settings
  в SubscriptionService по-прежнему применяются.
- User-Agent, cached settings и responseRules всё равно обязательны: проверка
  middleware выполняется **раньше** ручного override. Пустой UA не спасается `/json`.

## 5. Какие признаки доступны

| Признак | Фактическое использование |
| --- | --- |
| user-agent | Default app rules; отдельно extended и JSON fallback |
| accept | Default BROWSER rule через contains text/html |
| Любой HTTP header | Можно указать headerName в пользовательском condition |
| x-remnawave-injected-short-uuid | Middleware добавляет shortUuid из path в matcher headers; перекрывает одноимённый входной header |
| x-hwid | HWID-проверка; при пользовательском condition может участвовать в выборе, но default rules его не используют |
| x-device-os, x-ver-os, x-device-model | Метаданные устройства, а не встроенный app classifier |
| clientType из path | Явное сопоставление формата, не определение названия приложения |

IP сохраняется в context, но стандартный matcher не имеет condition для IP/URL/query;
он проверяет headers. Правило по shortUuid возможно через injected header.
Content-Type запроса, расширения User-Agent и device OS не создают скрытых capability rules.

### Две разные обработки User-Agent

Middleware:

```ts
const userAgent = truncateHeader(req.headers['user-agent']);
```

truncateHeader берёт первый элемент array и первые 512 JS UTF-16 code units. Этот UA
попадает в context, extended detector, JSON fallback и историю запросов.
Но matcher получает `{...req.headers, ...headersToAppend}` — **исходные** headers.
Для condition массив header values соединяется через запятую, длинный header не обрезается.

В результате UA длиной >512 может совпасть с rule по части за лимитом, хотя extended/fallback
её не увидят. Массив `['Unknown/1','SFI/1']` matcher видит как `Unknown/1,SFI/1`, а extended
detector — как Unknown/1. Пустой первый элемент array блокирует запрос ещё до matching.
Whitespace UA не trim-ится: строка из пробелов truthy, проходит обязательную проверку,
но anchored app regex обычно не совпадает и остаётся default fallback.

## 6. Алгоритм matcher и операторы

```ts
for (const rule of responseRules.rules) {
    if (!rule.enabled) continue;
    if (this.matchRule(rule, requestHeaders)) {
        return { matched: true, matchedRule: rule, responseType: rule.responseType };
    }
}
return { matched: false };
```

Rules не объединяются и не сортируются по специфичности. Отключённая rule пропускается.
**conditions=[] всегда true**, даже при operator=OR: отдельная проверка выполняется
до AND/OR. Непустые AND → every, OR → some, с short circuit.
No match → middleware 403. XRAY_BASE64 fallback существует только потому, что
default config содержит последнюю безусловную rule. Удаление её не даёт автоматический Base64.

Condition:

1. condition.headerName привести к lowercase; lookup в dictionary исходных requestHeaders.
   Express headers обычно уже lowercase; matcher сам не нормализует keys dictionary.
2. Array value → join(','); undefined → **false для любого operator**, включая отрицательные.
3. caseSensitive=false → lowercase и headerValue, и condition.value.
4. Выполнить operator. Ошибка condition логируется, результат false.

| Operator | Семантика |
| --- | --- |
| EQUALS / NOT_EQUALS | Точное равенство / неравенство всей строки |
| CONTAINS / NOT_CONTAINS | Наличие / отсутствие substring |
| STARTS_WITH / NOT_STARTS_WITH | Префикс / отсутствие префикса |
| ENDS_WITH / NOT_ENDS_WITH | Суффикс / отсутствие суффикса |
| REGEX / NOT_REGEX | JS new RegExp(value, caseSensitive ? '' : 'i').test(value), либо отрицание |

Regex — строка без внешних `/.../flags`. Anchors нужны внутри pattern. Invalid regex
возвращает false **также для NOT_REGEX**; нормальный settings parser заранее проверяет
исходные regex conditions и additionalExtendedClientsRegex, включая disabled rules.
HeaderName должен соответствовать token syntax, value length 1..255, caseSensitive обязателен.

Необычная семантика исходника: при caseSensitive=false **сам regex pattern тоже lowercased**.
Например, `\D+` превращается в `\d+`, меняя значение с non-digits на digits.
Parser проверяет исходную строку, а runtime работает с преобразованной. В совместимом
Python-порте нельзя незаметно заменить это одним re.IGNORECASE без lowercase pattern.

## 7. Полный default порядок

Источник — SRR_DEFAULT_CONFIG. Все шесть rules enabled=true и operator=AND.

| Позиция | name | Condition | Response type |
| --- | --- | --- | --- |
| 1 | Browser Subscription | accept CONTAINS text/html, case-sensitive | BROWSER |
| 2 | Mihomo Clients | user-agent REGEX, case-insensitive, pattern ниже | MIHOMO |
| 3 | Stash (iOS, macOS) | user-agent REGEX `^stash`, case-insensitive | STASH |
| 4 | Sing-box clients | user-agent REGEX `^sfa\|sfi\|sfm\|sft\|karing\|singbox`, case-insensitive | SINGBOX |
| 5 | Clash Core Clients | user-agent REGEX `^clash`, case-insensitive | CLASH |
| 6 | Fallback Base64 | conditions=[] | XRAY_BASE64 |

Полные patterns (plain regex, не JSON escaping):

```text
MIHOMO:
^(?:flclash|rabbit|flowvy|murge|mihomo|prizrak-box|koala-clash|clash(?:-verge|-nyanpasu|x meta|[-.]?meta))

STASH:
^stash

SINGBOX:
^sfa|sfi|sfm|sft|karing|singbox

CLASH:
^clash
```

Особенности, влияющие на перенос:

- BROWSER первым: любой app UA с Accept, содержащим text/html, получает info response.
  Это substring check, не HTTP content negotiation: `text/html;q=0` тоже совпадает;
  `TEXT/HTML` не совпадает; отсутствие Accept даёт false и позволяет app rules.
- MIHOMO должен стоять раньше общего CLASH, иначе clash-verge/meta попадут в legacy builder.
- В SINGBOX regex `^` относится **только к sfa**. sfi/sfm/sft/karing/singbox совпадают
  в любом месте строки. `prefix SFI/1` → SINGBOX. Не исправлять на
  `^(?:sfa|sfi|sfm|sft|karing|singbox)` без отдельного изменения поведения.
- Literal `sing-box/1` не подходит под `singbox`; special rule для него в default нет.
- Нет boundaries по окончанию имени: anchored prefix допускает дополнительный хвост
  приложения. Это не полноценное разбиение `App/Version`.
- Изменённый порядок и пользовательские rules могут полностью изменить таблицу.

## 8. Таблица приложений по default UA

Условия таблицы: базовый URL, отсутствие Accept:text/html, исходные default rules,
подписка разрешена, custom remarks не сделали ранний возврат. Значения UA ниже —
синтетические тестовые строки, а не наблюдение реального HTTP-запроса каждой версии приложения.

| UA / семейство префиксов | Первоначальный формат | При serveJsonAtBaseSubscription=true | Extended built-in |
| --- | --- | --- | --- |
| FlClash/1 | MIHOMO | MIHOMO | Нет |
| FlClashX/1, FlClash X/1 | MIHOMO | MIHOMO | Да |
| Rabbit/1, Murge/1, Mihomo/1 | MIHOMO | MIHOMO | Нет |
| Flowvy/1 | MIHOMO | MIHOMO | Да |
| prizrak-box/1, koala-clash/1 | MIHOMO | MIHOMO | Да |
| clash-verge/1, Clash-Nyanpasu/1 | MIHOMO | MIHOMO | Нет |
| ClashX Meta/1, ClashMeta/1, Clash-Meta/1, Clash.Meta/1 | MIHOMO | MIHOMO | Нет |
| Clash/1, ClashX/1, Clash Meta/1 | CLASH | CLASH | Нет |
| Stash/1 | STASH | STASH | Нет |
| SFA/1, SFI/1, SFM/1, SFT/1 | SINGBOX | SINGBOX | Нет |
| Karing/1, singbox/1 | SINGBOX | SINGBOX | Нет |
| Happ/1, INCY/1 | XRAY_BASE64 | XRAY_JSON | Да |
| Streisand/1, streisand/1 | XRAY_BASE64 | XRAY_JSON | Нет |
| ktor-client/1, V2Box/1, io.github.saeeddev94.xray/1 | XRAY_BASE64 | XRAY_JSON | Нет |
| v2rayNG/1.0.0, v2rayN/7.0.0, v2plus/1.2.3 | XRAY_BASE64 | XRAY_JSON | Нет |
| Hiddify/1, FoxRay/1, NekoBox/1, Shadowrocket/1 | XRAY_BASE64 | XRAY_BASE64 | Нет |
| sing-box/1, Unknown/1 | XRAY_BASE64 | XRAY_BASE64 | Нет |

Последние строки показывают отсутствие отдельной default сигнатуры, а не заключение,
что приложение поддерживает только Base64. Для нового UA сначала нужно наблюдать
реальный запрос и проверить формат на клиенте, затем добавить rule либо дать явный URL.

В `response-rules-examples.ts` есть пример **Block Legacy Clients** для CONTAINS Hiddify/FoxRay.
Это пример для редактора, а не активная default rule. Само наличие такого примера
не означает блокировку этих приложений. Источник:
[response-rules-examples.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/libs/contract/models/response-rules/response-rules-examples.ts).

## 9. Отдельный detector extended clients

Встроенные patterns, case-sensitive, без lowercase или flags:

```text
^FlClash ?X/
^Flowvy/
^prizrak-box/
^koala-clash/
^Happ/
^INCY/
```

Сначала any built-in match, затем по порядку additionalExtendedClientsRegex из
**совпавшей** rule. Custom patterns — new RegExp(pattern), кеш по строке pattern;
invalid regex, дошедший до middleware, попадает в общий next(error).
Custom regex может добавить extended apps, но не отменяет built-in true.
Проверяется context UA после truncate, а не заголовок matcher-а.

`flclashX/1` получает MIHOMO из case-insensitive default, но extended=false.
`FlClashX/1` → extended=true. Это независимые регистровые правила.
Ручной суффикс не имеет matchedRule: custom extended patterns не применяются,
встроенные продолжают применяться.

| Формат | Extended output |
| --- | --- |
| XRAY_BASE64 | `?serverDescription=<Base64>` после уже полного URI, включая fragment |
| XRAY_JSON | meta.serverDescription с декодированным UTF-8 описанием |
| MIHOMO | proxy.serverDescription с декодированным UTF-8 описанием |
| STASH | Dispatcher принудительно extended=false |
| CLASH / SINGBOX | Генераторы не используют extended flag |

Extended mode не выбирает другой формат и сам по себе не включает age encryption,
JSON fallback или поддержку дополнительных транспортов.

## 10. Поздний Base64 → Xray JSON fallback

В SubscriptionService после settings/squad overrides и успешного HWID-прохождения:

```ts
if (
    srrContext.subscriptionSettings.serveJsonAtBaseSubscription &&
    srrContext.matchedResponseType === 'XRAY_BASE64' &&
    !srrContext.ignoreServeJsonAtBaseSubscription
) {
    if (isJsonSubscriptionFallbackSupported(srrContext.userAgent)) {
        srrContext.matchedResponseType = 'XRAY_JSON';
    }
}
```

serveJsonAtBaseSubscription по initial seed=false, external squad может его заменить.
Rule modification ignoreServeJsonAtBaseSubscription=true запрещает переключение.
Никакого преобразования MIHOMO/CLASH/STASH/SINGBOX в JSON эта ветка не делает.

JSON fallback patterns, case-sensitive:

```text
^[Ss]treisand
^Happ/
^INCY/
^ktor-client
^V2Box
^io\.github\.saeeddev94\.xray/
^v2rayNG/(\d+\.\d+\.\d+)
^v2rayN/(\d+\.\d+\.\d+)
^v2plus/(\d+\.\d+\.\d+)
```

Regex.test используется как boolean. Захваченная версия **не парсится и не сравнивается**:
v2rayNG/0.0.1 подходит, v2rayNG/1.2 не подходит. Нет проверки реальных возможностей ядра.
Конечного `$` нет: suffix после подходящей тройки версии не препятствует совпадению.
Для Streisand меняется только первая буква: STREISAND/1 не подходит. Ряд patterns
не требует `/` или строгой границы имени: streisandWhatever тоже подходит.

Переключение находится после нескольких ранних return:

- BROWSER сразу возвращает info API.
- respondWithRemarks возвращает выбранный формат до JSON upgrade.
- HWID-denied может вернуть пустое body или dummy remarks в первоначальном формате.
- Неизвестный user возвращает not-found до upgrade.

Поэтому одна и та же Happ UA при успешной подписке может получить JSON, а при HWID-denied
fallback — Base64. Это следствие порядка кода, а не отдельного app mapping.
После upgrade загрузка hidden hosts и renderer используют уже XRAY_JSON.
matchedRuleName остаётся первоначальным, например Fallback Base64; записываемый в
историю matchedResponseType становится XRAY_JSON.

## 11. Modifications и шаблоны

Выбранная rule может изменить выдачу сверх самого responseType:

| Modification | Влияние |
| --- | --- |
| subscriptionTemplate | Имя общего шаблона; приоритет над external squad template name |
| ignoreHostXrayJsonTemplate | Для Xray JSON игнорировать template конкретного хоста |
| ignoreServeJsonAtBaseSubscription | Оставить Base64, запретить поздний JSON upgrade |
| additionalExtendedClientsRegex | Только extended flag, не формат |
| disableHwidCheck | Пропустить общий HWID check в этой ветке |
| excludeHostsByTags | Удалить соответствующие hosts до resolver fallback |
| respondWithRemarks | Непустой массив вызывает ранний fallback без реальных hosts |
| headers / applyHeadersToEnd | Установить headers раньше либо при финальной отправке |
| encryption | Зашифровать сериализованный body age1/age1pq1 и выдать text/plain |

Непустой массив respondWithRemarks из **одного** элемента тоже вызывает раннюю ветку;
текст schema description «more than one» не отражает фактическую проверку `.length > 0`.
Fallback dummy-конфиги и отключённый isShowCustomRemarks описаны в
[common.md](subscriptions/common.md). Выбранный формат при fallback не пересчитывается
по содержимому remarks.

Порядок template selection: имя rule, если есть; иначе имя external squad для response type;
в XRAY_BASE64 случае squad lookup заранее использует XRAY_JSON, учитывая возможный upgrade.
Именованный шаблон при отсутствии заменяется Default того же type. Собственный host
template XRAY_JSON выигрывает у общего template, пока ignoreHostXrayJsonTemplate=false.
После initial rule match external squad responseRules заново не сопоставляются.

Content-Type final body не всегда раскрывает format: CLASH/MIHOMO/STASH все text/yaml,
XRAY_JSON/SINGBOX оба application/json, а age ciphertext всегда text/plain.
BROWSER отправляет info object напрямую, минуя обычный body encryption/finalizer;
это не клиентский HTML/config generator. Подробности: [raw.md](subscriptions/raw.md).

## 12. Как подбирать формат для переноса

Следующий процесс — **рекомендация для реализации**, отдельно от существующих rules:

1. Зафиксировать реальный User-Agent, Accept, явный URL suffix и нужную версию клиента.
2. Сначала прогнать запрос через действующие rules, сохранив имя совпадения и причину выбора.
3. Выбрать целевое семейство: Mihomo → MIHOMO, legacy Clash → CLASH, Stash → STASH,
   sing-box → SINGBOX, Xray full config → XRAY_JSON, импорт URI → XRAY_BASE64.
   Семейство подтверждать по реальному приложению, а не подстроке произвольной UA.
4. Сверить доступные протоколы/транспорты с
   [матрицей генераторов](subscriptions/README.md): CLASH исключает VLESS,
   SINGBOX исключает XHTTP/KCP и custom VLESS encryption, STASH исключает XHTTP.
5. Для нового app добавить узкую rule до общих family/fallback rules либо предоставить
   явный suffix. Включать additionalExtendedClientsRegex только при поддержке extension.
6. Проверить импорт и обновление подписки клиентом; отдельно проверить handshake и
   extension/encryption. Успешный UA match не означает успешное соединение.

Не следует выбирать CLASH всем приложениям с подстрокой clash, JSON всем клиентам с
подстрокой box или пытаться автоматически превращать пустой результат фильтров в другой
формат. Исходник этого не делает; такая адаптация была бы новым поведением.

Пример **пользовательской** rule для подтверждённого нового Mihomo-клиента; это не default:

```json
{
  "version": "1",
  "settings": {"disableSubscriptionAccessByPath": false},
  "rules": [
    {
      "name": "MyApp Mihomo",
      "enabled": true,
      "operator": "AND",
      "conditions": [{
        "headerName": "user-agent",
        "operator": "REGEX",
        "value": "^myapp/",
        "caseSensitive": false
      }],
      "responseType": "MIHOMO",
      "responseModifications": {
        "subscriptionTemplate": "MyApp",
        "additionalExtendedClientsRegex": ["^MyApp/"]
      }
    },
    {
      "name": "Fallback Base64",
      "enabled": true,
      "operator": "AND",
      "conditions": [],
      "responseType": "XRAY_BASE64"
    }
  ]
}
```

Пример намеренно показывает минимальный custom ruleset; при реальном редактировании
вставить новую rule в существующий список, сохранив Browser и другие нужные family rules.
Вместо custom matching можно дать `/sub/<shortUuid>/mihomo`, но rule modifications из
примера тогда не будут применены.

## 13. Что сохранять в Python

Предлагаемые независимые функции:

```text
parse_and_validate_response_rules(config)
match_response_rules(config, original_headers, override_client_type)
detect_extended_client(truncated_ua, matched_rule)
apply_rule_modifications(context, matched_rule)
resolve_effective_settings_and_templates(user, context)
maybe_upgrade_base64_to_json(context)  # только в исходной позиции service pipeline
render_subscription(context, resolved_hosts)
```

Рекомендуемая модель результата хранит initialResponseType и effectiveResponseType,
matchedRuleName, isExtendedClient, overrideClientType и reason. Это улучшение наблюдаемости;
в исходном context matchedResponseType мутируется, отдельного initial-поля нет.

Обязательные детали совместимости:

- Python `all([])`/`any([])` не заменяют отдельное правило conditions=[] → true при OR.
- Missing header и пустой header различаются; отрицательный operator на missing → false.
- Перед lookup нормализовать HTTP header keys на transport boundary; не менять matcher
  array join и наличие двух разных UA-представлений.
- JS `.slice(0,512)` считает UTF-16 units, Python slicing — Unicode code points.
- Regex применять через search, не fullmatch; anchors из pattern сохранять.
- В case-insensitive conditions воспроизвести lowercase pattern/header + flag i;
  builtin extended/fallback patterns не lowercase-ить.
- ECMAScript RegExp и Python re имеют разные синтаксис/Unicode/case folding. Для
  произвольных пользовательских regex нужна явно определённая стратегия совместимости;
  default patterns можно переносить как ограниченный проверенный набор.
- Manual path не имеет matchedRule; не подтягивать modifications «подходящего по UA» правила.
- Сохранить положение upgrade после early returns; не переносить его в middleware.
- format support, extended metadata, HWID и encryption держать отдельными признаками.

## 14. Наблюдаемость и проверка нового приложения

Service пишет userAgent, matchedRuleName, matchedResponseType в subscription request history
на обычном пути успешной генерации. Не все ранние/заблокированные запросы проходят этот
участок; отсутствие записи не доказывает отсутствие запроса.

В статистике приложения имя извлекается SQL: если в UA есть `/`, взять часть до первого `/`,
иначе часть до первого пробела. В статистике HWID устройств используется часть до `/`.
Это группировка статистики, **не алгоритм выбора формата**. Нельзя переносить статистический
`app` как classifier вместо response rules.

Источники:
[user-subscription-request-history.repository.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/user-subscription-request-history/repositories/user-subscription-request-history.repository.ts),
[hwid-user-devices.repository.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/hwid-user-devices/repositories/hwid-user-devices.repository.ts).

Для диагностического запроса использовать тестового пользователя и вымышленные значения:

```bash
curl -i 'https://panel.example/sub/TEST_SHORT_UUID' \
  -H 'User-Agent: MyApp/1.0.0' \
  -H 'Accept: */*'
```

Это пример команды, при подготовке документации внешний запрос не выполнялся. Диагностика:
сначала проверить rule/type и override flags, затем effective format после JSON upgrade,
далее шаблон/exclusions и только затем содержимое body. Для проверки browser branch
изменить Accept на text/html; для ручного выбора добавить нужный suffix.

## 15. Проверки и границы подтверждения

При подготовке выполнена **71 изолированная проверка** исходных TypeScript matcher,
middleware и detector helpers. Загружены исходные default rules, NestJS decorators/logger,
query bus/settings и HTTP response подставлены; приложение и БД не запускались.
Проверены synthetic UA для 36 случаев, default приоритет, шесть suffix mappings,
path-disable/no-match, OR с пустыми conditions, missing negative condition, array headers,
regex lowercase, extended case sensitivity, version pattern без min-version,
UA truncation и custom modifications/manual override.
Полный SubscriptionService и реальные версии клиентских приложений не запускались;
положение JSON upgrade и early returns подтверждено чтением исходника.

Ключевые сценарии будущей приёмки:

| Вход / условие | Ожидаемый результат |
| --- | --- |
| UA=Mihomo/1, Accept=text/html;q=0 | BROWSER |
| UA=Mihomo/1, Accept=TEXT/HTML | MIHOMO |
| UA=Clash.Meta/1 | MIHOMO, а не CLASH |
| UA=Clash Meta/1 | CLASH |
| UA=prefix SFI/1 | SINGBOX из-за unanchored alternative |
| UA=sing-box/1 | XRAY_BASE64 |
| UA=Happ/1, default settings | XRAY_BASE64, extended=true |
| UA=Happ/1, serveJson=true, успешный normal service path | XRAY_JSON, extended=true |
| UA=Happ/1, serveJson=true, ignoreServeJson=true | XRAY_BASE64 |
| UA=Happ/1, serveJson=true, HWID-denied/remarks early return | Upgrade ещё не выполнен |
| UA=v2rayNG/0.0.1 | JSON fallback helper=true, без min-version проверки |
| UA=v2rayNG/1.2 | JSON fallback helper=false |
| UA=flclashX/1 | MIHOMO, extended=false |
| UA=FlClashX/1 | MIHOMO, extended=true |
| UA отсутствует, suffix=json | Middleware 403 |
| UA валиден, Accept=text/html, suffix=json | XRAY_JSON; matchedRule отсутствует |
| disableSubscriptionAccessByPath=true, suffix=json | BLOCK/403 |
| UA валиден, suffix=base64 | BLOCK/403 |
| rules=[], UA валиден | No match → 403 |
| conditions=[], operator=OR | Rule совпадает |
| Header отсутствует, NOT_EQUALS | Condition=false |
| caseSensitive=false, pattern=`\D+`, header=123 | Pattern lowercased в `\d+`, совпадает |
| UA='x'×512 + 'SFI/1' | Matcher SINGBOX, context UA без хвоста SFI/1 |
| Custom extended regex + manual suffix | Custom detector не применяется; встроенные patterns остаются |

Добавление rules под новые реальные приложения и исправление default regex/регистровых
особенностей должно оформляться отдельно от совместимого переноса алгоритма.
