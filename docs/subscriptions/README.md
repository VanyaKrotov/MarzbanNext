# Формирование клиентских конфигураций Remnawave: спецификация для переноса на Python

Документы описывают фактическое поведение `remnawave/backend` версии **3.4.5**, коммит
[`010b365ab1fabea01192b5e6ade4e98e66ee1dbd`](https://github.com/remnawave/backend/tree/010b365ab1fabea01192b5e6ade4e98e66ee1dbd)
от 2026-10-06. Анализ выполнен 2026-10-16–2026-10-17. Это спецификация существующей реализации,
а не обещание совместимости с любой версией клиентских ядер и не описание текущего генератора MarzbanNext.
Имена форматов и URL MarzbanNext описаны в [актуальном контракте](../subscription-templates.md).
В панели принимаются только `v2ray`, `v2ray-json`, `clash`, `sing-box`, `outline`, без алиасов.

## Документы

Идентификация приложений, default UA rules и выбор формата: [../apps.md](../apps.md).

| Документ | Содержание |
| --- | --- |
| [common.md](common.md) | Выбор хостов, объединение с инбаундами и пользователем, `ResolvedProxyConfig`, криптография, шаблоны названий, fallback, mapper и различия JS/Python |
| [xray-base64.md](xray-base64.md) | VLESS/Trojan/Shadowsocks/Hysteria2 URI, plaintext и Base64, query-параметры, экранирование |
| [xray-json.md](xray-json.md) | Клиентские Xray outbounds, шаблоны, TLS/Reality, XHTTP, injector нескольких хостов |
| [clash.md](clash.md) | Обычный Clash: Trojan/SS, YAML, группы и ограничения |
| [mihomo.md](mihomo.md) | Mihomo: VLESS, Reality, XHTTP, Hysteria2, smux, providers и YAML |
| [stash.md](stash.md) | Ветка Stash общего Mihomo-генератора и её отличия |
| [singbox.md](singbox.md) | sing-box 1.13.x: JSON outbounds, multiplex, Hysteria2 и selector/urltest |
| [raw.md](raw.md) | Raw API с промежуточными конфигурациями; отличие от browser/info API |

Рекомендуемый порядок чтения: `common.md` → нужный формат → его проверочные сценарии.
В документах «совместимый перенос» означает сохранение наблюдаемого результата, включая
пропущенные поля, неожиданные значения по умолчанию и ограничения исходного генератора.
Предлагаемые Python-интерфейсы и проверки обозначены отдельно от исходного поведения.

## Полный путь данных

```text
серверный Xray config profile
  → ConfigProfileInbounds.rawInbound
  → выбор hosts по пользователю и internal squads
  → HostWithRawInbound (host + rawInbound + необязательный Xray JSON template)
  → ResolveProxyConfigService.resolveProxyConfig()
  → ResolvedProxyConfig[]
  → RenderTemplatesService.generateSubscription()
  → генератор формата + клиентский шаблон + mapper
  → JSON / YAML / URI → необязательное шифрование HTTP-body
```

Серверный инбаунд предоставляет параметры соединения и протокола. Локальные клиентские
`inbounds`, DNS и маршрутизация в полном JSON/YAML берутся из **клиентского шаблона**.
Внешние адрес и порт подключения задаются хостом, а не `listen`/`port` серверного инбаунда.

## Матрица форматов

| Response type | Генератор | Результат | Content-Type |
| --- | --- | --- | --- |
| `XRAY_BASE64` | `XrayGeneratorService` | Base64 от строк URI через LF | `text/plain` |
| `XRAY_JSON` | `XrayJsonGeneratorService` | JSON-массив полных клиентских конфигов | `application/json` |
| `CLASH` | `ClashGeneratorService` | Один YAML-документ | `text/yaml` |
| `MIHOMO` | `MihomoGeneratorService`, `isStash=false` | Один YAML-документ | `text/yaml` |
| `STASH` | `MihomoGeneratorService`, `isStash=true` | Один YAML-документ | `text/yaml` |
| `SINGBOX` | `SingBoxGeneratorService` | Один JSON-объект | `application/json` |
| raw API | Только resolver | API envelope с `resolvedProxyConfigs` | JSON API |

`BROWSER` в публичном subscription endpoint возвращает объект информации о подписке с
`links`, а не HTML из генератора, несмотря на `text/html` в таблице констант.
`BLOCK`, `STATUS_CODE_404`, `STATUS_CODE_451`, `SOCKET_DROP` — действия response rules,
а не дополнительные форматы клиентских конфигураций.
`json` и `v2ray-json` в request type constants не создают отдельных генераторов.

| Возможность | URI | Xray JSON | Clash | Mihomo | Stash | sing-box |
| --- | --- | --- | --- | --- | --- | --- |
| VLESS | Да | Да | Исключается | Да | Да | Только `encryption=none` |
| Trojan, SS | Да | Да | Да | Да | Да | Да |
| Hysteria2 | Да | Да, Xray protocol `hysteria` | Исключается | Да | Да | Да |
| XHTTP | Да | Да | Исключается | Да | Исключается | Исключается |
| KCP | Да, только mtu/tti | Да | Исключается | Исключается | Исключается | Исключается |
| Host mapper | `base64` | `xrayJson` | Нет | `mihomo` | `mihomo` | `singbox` |
| Клиентский шаблон | Нет | Да | Да | Да | Да | Да |

«Да» в таблице означает наличие ветки генерации; совместимость произвольных сочетаний
протокола, транспорта и security отдельно не валидируется.

## План переноса

1. Выделить Python-модель промежуточной конфигурации и совместимые операции JS:
   truthiness, отсутствие значения, `String`, `Number`, `parseInt`, URI escaping.
2. Перенести resolver как самостоятельный слой; инъецировать время и случайность.
3. Перенести общий mapper и загрузку клиентских шаблонов.
4. Перенести URI и Xray JSON, затем YAML-генераторы и sing-box.
5. Сохранить порядок хостов, outbounds, групп, параметров URI и mapper-операций.
6. Сравнить результаты с TypeScript-реализацией на фиксированных входных данных.
   Для JSON/YAML сначала сравнивать структуру; для URI/Base64 — байты.
7. Проверить отдельно HTTP-выбор формата, HWID/fallback, заголовки и age-шифрование.

В MarzbanNext уже существуют классы в `app/subscription/` (`v2ray.py`, `clash.py`,
`singbox.py`, `outline.py`). Сопоставление с ними — отдельный этап реализации:
не следует автоматически приравнивать их поведение к Remnawave или добавлять Outline
в перечень форматов Remnawave.

## Источники и пределы проверки

Основные исходники:

- [render-templates.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/render-templates.service.ts)
- [config-types.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/constants/config-types.ts)
- [subscription.service.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/subscription.service.ts)
- [subscription.controller.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription/controllers/subscription.controller.ts)
- [default-templates.ts](https://github.com/remnawave/backend/blob/010b365ab1fabea01192b5e6ade4e98e66ee1dbd/src/modules/subscription-template/constants/default-templates.ts)

Все ссылки закреплены за коммитом. Примеры используют вымышленные значения и
показывают генерацию, а не успешное подключение. Проверочные сценарии — требования
к будущему порту; они не означают, что Python-перенос уже реализован.

При подготовке документации выполнены 28 проверок исходных TypeScript-функций в
изолированном стенде: генераторы транспилированы без запуска NestJS, шаблоны и framework
services подставлены, использованы доступные локальные lodash/js-yaml. Проверены
URI/Base64, UUID route, unsupported filters, WS early data и headers, fingerprint,
sing-box parsers/multiplex, Xray injector selection/tags, mapper array holes и отдельные
ветки resolver. Примеры outbound/proxy/URI сверены с полученными результатами.
Криптографические helper-карты и TemplateEngine в этом стенде подставлены: PQC,
полный шаблонный движок, Redis/БД, HTTP/HWID и реальные клиенты runtime-проверку не проходили.
