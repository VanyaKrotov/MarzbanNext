# XHTTP extra

В форме хоста добавьте **Дополнительные параметры XHTTP** и нажмите **Настроить**. В Monaco вводится
сам объект дополнительных параметров, без обёртки `transport.xhttp.extra`:

```json
{
  "uplinkHTTPMethod": "PUT",
  "xmux": {
    "maxConnections": "2-4",
    "hMaxRequestTimes": "600-900"
  }
}
```

Для API этот объект находится в `overrides.transport.xhttp.extra`. Адрес, порт,
Host и путь задаются обычными полями хоста; режим XHTTP (`mode`) берётся из инбаунда.
Добавлять эти поля в корневой `extra` нельзя. Отдельные Host/путь/режим доступны
внутри `downloadSettings.xhttpSettings`.

Схема содержит все дополнительные поля XHTTP из
[Xray SplitHTTPConfig](https://github.com/XTLS/Xray-core/blob/1b1647cd9ddf0abc34b981d4611fc03bcac1ca74/infra/conf/transport_method.go).
Она доступна в `GET /api/hosts/capabilities` и используется редактором для
автодополнения, справки по наведению, примеров и проверки типов/диапазонов.
Неизвестные поля отклоняются. В начале пустого документа доступны готовые примеры
метода, GET, XMUX и отдельного download-соединения.

## Наследование и сохранение

- Без переопределения сохраняется `extra` инбаунда. Если у инбаунда нет `extra`,
  наследуются его дополнительные поля из `xhttpSettings`/`splithttpSettings`.
- Явный объект **целиком заменяет** дополнительные параметры инбаунда,
  в том числе при PATCH. Его отсутствующие ключи используют значения по умолчанию ядра.
- `{}` очищает унаследованные дополнительные параметры. Удаление поля в форме
  или `extra: null` в PATCH возвращает наследование.
- `null` внутри `extra` запрещён. `false`, `0`, `""`, пустые объекты и исходное
  написание диапазонов сохраняются; значения по умолчанию не записываются в БД.
- Существующий `scMaxConcurrentPosts` сохраняется для старых клиентов.
  В текущем Xray этого параметра уже нет; Monaco помечает его устаревшим.

Миграция БД не требуется: расширяется проверка существующего JSON-объекта.

## Числа и диапазоны

В таблицах ниже **range** означает целое число, числовую строку или строку
с диапазоном: `3`, `"3"`, `"2-4"`. Поддерживаются обратные границы (`"4-2"`),
знаки (`"+2"`, `"-2--1"`) и пустая строка (`""`, нулевой диапазон).
Каждая граница должна помещаться в signed int32: от −2147483648 до 2147483647.
Пробелы внутри диапазона, дроби, boolean и переполнение отклоняются.
Панель сохраняет исходное представление; Xray упорядочивает границы при чтении.

Значение `0` обычно включает default ядра, а не отключает функцию.
Дополнительные ограничения указаны у отдельных полей. Возможность записать
отрицательный range соответствует парсеру Xray и не делает отрицательные размеры
или интервалы подходящими для работы; для них используйте положительные значения
или документированный нулевой default.

## HTTP, padding и ограничения потока

| Параметр | Тип / пример | Назначение и ограничения |
| --- | --- | --- |
| `uplinkHTTPMethod` | string: `"PUT"` | HTTP-метод upload. По умолчанию `POST`. Обрезается по краям и переводится в верхний регистр; допустим HTTP token длиной до 32 символов. `GET` разрешён только при `mode: "packet-up"`. |
| `headers` | object: `{"User-Agent":"Mozilla/5.0"}` | Строковые HTTP-заголовки. Ключ `Host` в любом регистре запрещён: используйте поле Host. Имена должны быть HTTP token, значения без CR/LF/NUL. |
| `xPaddingBytes` | range: `"100-1000"` | Размер padding в байтах. Обе ненулевые границы положительные; `0`/`""` включают default 100–1000. Отключить padding этим полем нельзя. |
| `xPaddingObfsMode` | boolean: `true` | Включает настраиваемые место и способ padding. При `false` используется прежний padding в Referer. |
| `xPaddingKey` | string: `"x_padding"` | Имя query/cookie с padding; пустая строка использует `x_padding`. |
| `xPaddingHeader` | string: `"X-Padding"` | Имя заголовка padding; пустая строка использует `X-Padding`. |
| `xPaddingPlacement` | enum | `cookie`, `header`, `query`, `queryInHeader`; `""` использует `queryInHeader`. |
| `xPaddingMethod` | enum | `repeat-x`, `tokenish`; `""` использует `repeat-x`. |
| `noGRPCHeader` | boolean: `false` | Не добавлять `Content-Type: application/grpc` в потоковом upload. |
| `noSSEHeader` | boolean: `false` | Серверный параметр: не добавлять `Content-Type: text/event-stream` в download-ответ. |
| `scMaxEachPostBytes` | range: `1000000` | Размер packet-up POST в байтах; `0` использует 1000000. Размеры на клиенте и сервере должны быть совместимы. |
| `scMinPostsIntervalMs` | range: `"10-30"` | Минимальный интервал packet-up запросов, мс; `0` использует 30. |
| `scMaxBufferedPosts` | int64 ≥ 0: `30` | Серверный буфер packet-up запросов на сессию; `0` использует 30. |
| `scStreamUpServerSecs` | range: `"20-80"` | Серверное время stream-up соединения, с; `0` использует 20–80. |
| `serverMaxHeaderBytes` | int32 ≥ 0: `16384` | Серверный предел размера HTTP-заголовков, байты; `0` использует 8192. |
| `scMaxConcurrentPosts` | range: `100` | Устаревший предел параллельных POST; сохранён для совместимости со старыми настройками. |

Серверные параметры в клиентской подписке не перенастраивают инбаунд ноды.
Для изменения поведения сервера задайте соответствующие значения в его конфигурации.

## Сессия, последовательность и upload payload

| Параметр | Тип / пример | Назначение и ограничения |
| --- | --- | --- |
| `sessionIDPlacement` | enum: `"header"` | `path`, `cookie`, `header`, `query`; `""` использует `path`. |
| `sessionIDKey` | string: `"X-Session"` | Имя заголовка/cookie/query с ID. При пустом значении default `X-Session` для header, `x_session` для cookie/query. Для path не используется. |
| `sessionIDTable` | string: `"Base62"` | Набор ASCII-символов или готовый алфавит. `""` использует UUID. |
| `sessionIDLength` | range: `"16-24"` | Длина ID. При непустом алфавите обязательна, обе границы положительные; при UUID игнорируется. |
| `seqPlacement` | enum: `"query"` | Место номера пакета: `path`, `cookie`, `header`, `query`; `""` использует `path`. |
| `seqKey` | string: `"x_seq"` | Имя номера пакета. Default `X-Seq` для header, `x_seq` для cookie/query. |
| `uplinkDataPlacement` | enum: `"header"` | `auto`, `body`, `cookie`, `header`; `""` использует `auto`. Cookie/header требуют `packet-up`. |
| `uplinkDataKey` | string: `"X-Data"` | Префикс заголовков/cookie с данными; default `x_data` для cookie, `X-Data` для header. |
| `uplinkChunkSize` | range: `"3000-4000"` | Размер кодированного фрагмента данных, байты. Нулевой default: 2048–3072 для cookie, 3000–4000 для header, иначе `scMaxEachPostBytes`. Ненулевые границы ниже 64 ядро поднимает до 64. |

Готовые алфавиты: `ALPHABET`, `Alphabet`, `BASE36`, `Base62`, `HEX`, `alphabet`,
`base36`, `hex`, `number`. Регистр важен. Можно задать собственную ASCII-строку.
Число возможных ID должно быть не меньше 2³¹: например, `Base62` требует не менее
6 символов при фиксированной длине, `hex` — 8. Для диапазона учитывается сумма
числа вариантов всех допустимых длин. Эту совместную проверку выполняет API;
Monaco проверяет ASCII, наличие и положительность длины.

Настройки размещения и ключей на клиенте и сервере должны совпадать.
Пример upload через GET, когда у инбаунда установлен `mode: "packet-up"`:

```json
{
  "uplinkHTTPMethod": "GET",
  "uplinkDataPlacement": "header",
  "uplinkDataKey": "X-Data",
  "uplinkChunkSize": "3000-4000",
  "sessionIDPlacement": "header",
  "sessionIDKey": "X-Session",
  "sessionIDTable": "Base62",
  "sessionIDLength": "16-24"
}
```

Режим внешнего инбаунда проверяется сервером при сохранении хоста и при изменении
инбаунда. У вложенного `xhttpSettings` режим известен прямо из JSON, поэтому Monaco
также проверяет его совместимость с GET, cookie/header payload и `downloadSettings`.

## XMUX

`xmux` управляет повторным использованием HTTP-соединений XHTTP; это отдельный
механизм от обычного MUX. Все поля необязательны.

| Поле | Тип / пример | Значение |
| --- | --- | --- |
| `maxConcurrency` | range: `"8-16"` | Параллельные потоки на HTTP-соединение. |
| `maxConnections` | range: `"2-4"` | Число HTTP-соединений. |
| `cMaxReuseTimes` | range: `0` | Число повторных использований соединения; `0` не ограничивает. |
| `hMaxRequestTimes` | range: `"600-900"` | Число HTTP-запросов на соединение. |
| `hMaxReusableSecs` | range: `"1800-3000"` | Время повторного использования HTTP-соединения, с. |
| `hKeepAlivePeriod` | int64: `30` | HTTP/2 KeepAlive, с. `0` использует default ядра; отрицательное значение отключает. |

Положительные `maxConnections` и `maxConcurrency` взаимоисключающие, включая
числовые строки и диапазоны с положительной верхней границей. Проверка есть в API
и Monaco. Если весь объект XMUX нулевой/пустой, Xray задаёт пул из 3 соединений,
600–900 запросов и 1800–3000 с повторного использования. Это default **всего пула**,
а не автоматически добавляемые значения каждого отсутствующего поля.

## Отдельное download-соединение

`downloadSettings` описывает отдельный XHTTP stream. Его адрес и порт обязательны;
`network` (или прежний `method`) должен быть `xhttp`/`splithttp`. TCP и другие
транспорты здесь недопустимы. Внешний `mode: "stream-one"` исключает этот объект.

```json
{
  "uplinkHTTPMethod": "PUT",
  "downloadSettings": {
    "address": "download.example.com",
    "port": 443,
    "network": "xhttp",
    "security": "tls",
    "tlsSettings": {
      "serverName": "download.example.com",
      "alpn": ["h2"],
      "fingerprint": "chrome"
    },
    "xhttpSettings": {
      "host": "download.example.com",
      "path": "/download",
      "extra": {"xmux": {"maxConnections": "2-4"}}
    },
    "sockopt": {"tcpFastOpen": false}
  }
}
```

| Поле | Назначение |
| --- | --- |
| `address`, `port` | Непустой адрес сервера и целый порт 1–65535. |
| `network`, `method` | Транспорт XHTTP; `method` — прежнее имя с приоритетом над `network`. |
| `security` | `none`, `tls`, `reality`, `""`; без поля/при пустой строке используется none. |
| `tlsSettings` | Нативные TLS-поля: SNI, ALPN, fingerprint, сертификаты, версии TLS, cipherSuites, curvePreferences, проверка сертификатов, ECH и др. Все поля описаны во вложенной схеме. |
| `realitySettings` | Клиентские `serverName`, `fingerprint`, `password`/`publicKey`, `shortId`, `mldsa65Verify`, `spiderX`, `show`, `masterKeyLog`. При security=reality объект обязателен. `shortId` — чётное число hex-символов, до 16. Криптографические ключи проверяет ядро. |
| `xhttpSettings` | Собственные host/path/mode, дополнительные параметры и необязательный атомарный `extra` с теми же правилами. |
| `splithttpSettings` | Прежнее имя `xhttpSettings`; явный `xhttpSettings`, включая `{}`, имеет приоритет. |
| `sockopt` | [Схема параметров сокета](socket-options.md). Parent `sockopt.penetrate` может переопределить этот объект в Xray. |
| `finalmask` | [Схема Final mask](finalmask.md) для download-соединения. |

## Вывод в подписки

- **Xray JSON:** полный `extra` передаётся в XHTTP settings, включая вложенные
  download/TLS/REALITY/socket/FinalMask. Панель не подставляет defaults в сохранённый JSON.
- **URI / Base64:** `extra` передаётся JSON-параметром ссылки. VMess хранит объект
  `extra` внутри JSON payload до кодирования. Поддержку конкретных параметров обеспечивает клиент.
- **Clash:** общие параметры преобразуются в `xhttp-opts`: `uplink-http-method`,
  `session-placement`, `session-key`, `session-table`, `session-length`,
  `reuse-settings` и остальные нативные имена. Диапазоны передаются строками.
  `downloadSettings` преобразуется в `download-settings` с `server`, `port`,
  `path`, `host`, `headers`, `reuse-settings`, TLS/ALPN/SNI/fingerprint,
  проверкой имени сертификата и базовыми REALITY public-key/short-id.
  Настройки безопасности download не наследуются от upload случайно.
  У Clash нет эквивалентов всех Xray TLS/REALITY, сокетов и FinalMask: они
  остаются доступны в Xray/URI, но не копируются как Xray-объекты в Clash download.
  Серверные параметры и устаревшие поля могут игнорироваться клиентом.
  Структура сверена с [нативными типами Clash](https://github.com/MetaCubeX/mihomo/blob/Alpha/adapter/outbound/vless.go).
- **sing-box / Outline:** XHTTP не поддерживается генераторами этих форматов;
  такое подключение исключается из выдачи, остальные подключения сохраняются.

Схема описывает конфигурацию, а не проверку сети: доступность адреса, файлы
сертификатов и криптографические значения окончательно проверяются клиентским ядром.
