## [1.1.2](https://github.com/disafronov/skilled/compare/v1.1.1...v1.1.2) (2026-06-27)

## [1.1.2-rc.1](https://github.com/disafronov/skilled/compare/v1.1.1...v1.1.2-rc.1) (2026-06-27)

## [1.1.1](https://github.com/disafronov/skilled/compare/v1.1.0...v1.1.1) (2026-06-27)

### Bug Fixes

* bump cryptography upper bound to <49.0.0 to resolve 6 CVEs ([86bd971](https://github.com/disafronov/skilled/commit/86bd9712a8fd160cbe882275e48cdb5e5d2f0aa2))
* replace Signer-based field with actual Fernet encryption ([15dfb76](https://github.com/disafronov/skilled/commit/15dfb76f4f4d3dc08e99bc527dff11803dcffe80))

## [1.1.1-rc.1](https://github.com/disafronov/skilled/compare/v1.1.0...v1.1.1-rc.1) (2026-06-27)

### Bug Fixes

* bump cryptography upper bound to <49.0.0 to resolve 6 CVEs ([a30f144](https://github.com/disafronov/skilled/commit/a30f144439f5530c09a127bef037d493d01804ad))
* replace Signer-based field with actual Fernet encryption ([56f8dc9](https://github.com/disafronov/skilled/commit/56f8dc97f587556fbba68ea53aa85aaff5d0eb9a))

## [1.1.0](https://github.com/disafronov/skilled/compare/v1.0.1...v1.1.0) (2026-06-27)

### Features

* **jobs:** add admin retry actions ([73401d6](https://github.com/disafronov/skilled/commit/73401d638a26670da2987a4d3159b27659ea32b5))

### Bug Fixes

* dead code ([0aa76db](https://github.com/disafronov/skilled/commit/0aa76db62fdd9d87c8c0a828535fcdb6d49dba70))
* encrypt tokens at rest using EncryptedCharField ([cd815be](https://github.com/disafronov/skilled/commit/cd815be71399ace10ecea684581850508cc3063f))
* handle None content from LLM response instead of cast ([c9ab7db](https://github.com/disafronov/skilled/commit/c9ab7db48e3d8f6bf42dc58d0c1bebbb7032900d))
* **jobs:** backfill invalid finished jobs before constraints ([5d2b06b](https://github.com/disafronov/skilled/commit/5d2b06bed4791de5c07d2e82f6e08ad45b3eac81))
* **jobs:** make delivery selection safe and ordered ([7e9d9c3](https://github.com/disafronov/skilled/commit/7e9d9c35f0fe8559e3cd5d7ef1b6ea05bf037726))
* **telegram:** avoid leaking bot token in error tracebacks ([9c098dd](https://github.com/disafronov/skilled/commit/9c098ddbd11097b3cd4b7f3bdedee74590f6e64f))
* widen Q2 timeout/retry defaults for LLM latency ([cef455e](https://github.com/disafronov/skilled/commit/cef455ecce0d772f80e592fca5e036c7a91a3ed6))

### Performance Improvements

* **jobs:** add worker selection indexes ([d4dc119](https://github.com/disafronov/skilled/commit/d4dc11905ddf99be4d0cc6652ae3a07ef4850a3f))

## [1.1.0-rc.4](https://github.com/disafronov/skilled/compare/v1.1.0-rc.3...v1.1.0-rc.4) (2026-06-27)

### Bug Fixes

* handle None content from LLM response instead of cast ([d7ee4a0](https://github.com/disafronov/skilled/commit/d7ee4a0daae66a81dceea10d096a4347482f8199))

## [1.1.0-rc.3](https://github.com/disafronov/skilled/compare/v1.1.0-rc.2...v1.1.0-rc.3) (2026-06-27)

## [1.1.0-rc.2](https://github.com/disafronov/skilled/compare/v1.1.0-rc.1...v1.1.0-rc.2) (2026-06-27)

### Bug Fixes

* dead code ([1673843](https://github.com/disafronov/skilled/commit/167384313e63fd1beee4dab537eaa03ac8a12718))
* encrypt tokens at rest using EncryptedCharField ([91242fe](https://github.com/disafronov/skilled/commit/91242fed307f5949a97b4bfa02321983d75269ae))
* widen Q2 timeout/retry defaults for LLM latency ([17d5e21](https://github.com/disafronov/skilled/commit/17d5e21a1e999a7a917bc0a803d749bbe43e6c8b))

## [1.1.0-rc.1](https://github.com/disafronov/skilled/compare/v1.0.2-rc.2...v1.1.0-rc.1) (2026-06-27)

### Features

* **jobs:** add admin retry actions ([fd83ddb](https://github.com/disafronov/skilled/commit/fd83ddb8e50f9edfb7fd4dedae565bfdebefabe7))

## [1.0.2-rc.2](https://github.com/disafronov/skilled/compare/v1.0.2-rc.1...v1.0.2-rc.2) (2026-06-27)

### Bug Fixes

* **jobs:** backfill invalid finished jobs before constraints ([48513d6](https://github.com/disafronov/skilled/commit/48513d639227336d5408cadddcab62ccff4b5bb0))
* **jobs:** make delivery selection safe and ordered ([83eb42b](https://github.com/disafronov/skilled/commit/83eb42be22f0ccffd2da00d77b0b76b57835b4f7))
* **telegram:** avoid leaking bot token in error tracebacks ([f0e1638](https://github.com/disafronov/skilled/commit/f0e16387a8d338e51c614b6711c1f8b0fcf3b076))

## [1.0.2-rc.1](https://github.com/disafronov/skilled/compare/v1.0.1...v1.0.2-rc.1) (2026-06-27)

### Performance Improvements

* **jobs:** add worker selection indexes ([4092ed2](https://github.com/disafronov/skilled/commit/4092ed241014e46d5f05ab609d3a5ef489992f2d))

## [1.0.1](https://github.com/disafronov/skilled/compare/v1.0.0...v1.0.1) (2026-06-26)

### Bug Fixes

* **admin:** derive field order from models ([c433e21](https://github.com/disafronov/skilled/commit/c433e211fd750fe9791c544091448df3e3de58bc))
* **admin:** mask token fields ([4cd6de3](https://github.com/disafronov/skilled/commit/4cd6de3ddd38cf70d37b91e49b6f23bee481aa4a))
* **jobs:** prefix stale llm timeout setting ([6e70d74](https://github.com/disafronov/skilled/commit/6e70d7450b186a340f5ce0b60d4ea108288f1097))
* **jobs:** requeue stale llm jobs ([89d43af](https://github.com/disafronov/skilled/commit/89d43af027c0f2e5fe4d7942690cb670cb6c0e6f))

### Performance Improvements

* **jobs:** preload bot for telegram delivery ([29d7ec5](https://github.com/disafronov/skilled/commit/29d7ec58f1e9cbf33c408801eb579046150da919))

## [1.0.1-rc.3](https://github.com/disafronov/skilled/compare/v1.0.1-rc.2...v1.0.1-rc.3) (2026-06-26)

### Bug Fixes

* **jobs:** prefix stale llm timeout setting ([51706e2](https://github.com/disafronov/skilled/commit/51706e2e773c3c2505193846ba890015db475d5d))
* **jobs:** requeue stale llm jobs ([79f2436](https://github.com/disafronov/skilled/commit/79f24362ab17055917a07f4502f895a5322cbe91))

### Performance Improvements

* **jobs:** preload bot for telegram delivery ([bfc45dc](https://github.com/disafronov/skilled/commit/bfc45dc74ac08743f8df6aa7beb9c5decf299dfb))

## [1.0.1-rc.3](https://github.com/disafronov/skilled/compare/v1.0.1-rc.2...v1.0.1-rc.3) (2026-06-26)

### Bug Fixes

* **jobs:** requeue stale llm jobs ([79f2436](https://github.com/disafronov/skilled/commit/79f24362ab17055917a07f4502f895a5322cbe91))

### Performance Improvements

* **jobs:** preload bot for telegram delivery ([bfc45dc](https://github.com/disafronov/skilled/commit/bfc45dc74ac08743f8df6aa7beb9c5decf299dfb))

## [1.0.1-rc.3](https://github.com/disafronov/skilled/compare/v1.0.1-rc.2...v1.0.1-rc.3) (2026-06-26)

## [1.0.1-rc.2](https://github.com/disafronov/skilled/compare/v1.0.1-rc.1...v1.0.1-rc.2) (2026-06-26)

### Bug Fixes

* **admin:** derive field order from models ([2ae8d70](https://github.com/disafronov/skilled/commit/2ae8d703759cc086d0d3573407553347d9dec51e))
* **admin:** mask token fields ([2273878](https://github.com/disafronov/skilled/commit/22738784dbc12b1ddbec67cc6c5c6ea9fee0c38f))

## [1.0.1-rc.1](https://github.com/disafronov/skilled/compare/v1.0.0...v1.0.1-rc.1) (2026-06-26)

## 1.0.0 (2026-06-25)

### Features

* cron ([c8f1a80](https://github.com/disafronov/skilled/commit/c8f1a800b34aaffe3bf9c1d3260d4a56366f3bcb))
* **health:** add health check endpoints ([f7134bf](https://github.com/disafronov/skilled/commit/f7134bff944c5a1270638632912564d1cfa6d252))
* initial ([b442c2c](https://github.com/disafronov/skilled/commit/b442c2c9594094ee6303e334cb77256e5c0d12b4))
* **jobs:** batch Telegram messages per chat ([f2b71f8](https://github.com/disafronov/skilled/commit/f2b71f86fb18822ca2c5f4474b3ebdd11b5ff764))
* **llm:** load global policy from file ([2e68192](https://github.com/disafronov/skilled/commit/2e68192a34940d5baef7be7ea1b68cad8593bb63))
* redirect to admin ([1363c94](https://github.com/disafronov/skilled/commit/1363c94b39b3014b05ca0119d95df87855819a7b))
* **telegram:** acknowledge queueing and reply with results ([baa1905](https://github.com/disafronov/skilled/commit/baa190520bd2a11594c99407d690a70860846d7e))
* update ([1bc40bb](https://github.com/disafronov/skilled/commit/1bc40bb3362e85a90649ae12c826a2fba6a54e6c))
* update ([910629a](https://github.com/disafronov/skilled/commit/910629a775292ddd2d07fe3b5a70eda9e739aa72))

### Bug Fixes

* add typing to q2 operational code ([465c2d2](https://github.com/disafronov/skilled/commit/465c2d2bf05164174e1e5473794d814fc16196ca))
* explicit httpx timeouts + error handling + atomic offset persistence ([61e308f](https://github.com/disafronov/skilled/commit/61e308fe1e5af5ebbd392cbf0eac32c81aaebf45))
* harden q2 scheduling and telegram delivery ([a307e9e](https://github.com/disafronov/skilled/commit/a307e9ef7384387888f9bbddc2e22a0d3b88f6c6))
* **jobs:** join batched Telegram messages with spaces ([c21beda](https://github.com/disafronov/skilled/commit/c21beda958266be3b9d3d1ae44e355e916f4fbb4))
* **jobs:** refresh audit timestamps on state updates ([2b8eb9b](https://github.com/disafronov/skilled/commit/2b8eb9bd4836c33e84631a8fdb8e101f53327064))
* **jobs:** remove cron schedules ([303ae65](https://github.com/disafronov/skilled/commit/303ae657d673eba1129e2ea40d340ef1b51fbf61))
* **scheduler:** enforce managed q2 schedules ([e91e338](https://github.com/disafronov/skilled/commit/e91e3388690f80e31bceba397ab2c8799c015540))
* settings ([45ff78f](https://github.com/disafronov/skilled/commit/45ff78fc075e567a7187dbe9fc6541854064c876))
* settings ([25b282f](https://github.com/disafronov/skilled/commit/25b282f1f6a6d63f4913c5c140ddd4d0e2def7bf))
* silence flake8 in telegram markdown sanitization ([4c10c25](https://github.com/disafronov/skilled/commit/4c10c25c91cd5a2b0db955c5e89a314742f3e0f3))
* static ([ef90c47](https://github.com/disafronov/skilled/commit/ef90c476bd91020027145fc5129619bb3cf035e6))
* tasks ([29652f5](https://github.com/disafronov/skilled/commit/29652f5359008f3b205eb555257a7ae6db9411c2))
* **telegram:** surface api error response bodies ([aa21857](https://github.com/disafronov/skilled/commit/aa2185749032ea0971287c72c0ad06693d430b51))
* use standard cron schedule expressions ([767a335](https://github.com/disafronov/skilled/commit/767a3358758a7ba05be802fec12c26f67bd25bb4))

## [1.0.0-rc.7](https://github.com/disafronov/skilled/compare/v1.0.0-rc.6...v1.0.0-rc.7) (2026-06-25)

## [1.0.0-rc.6](https://github.com/disafronov/skilled/compare/v1.0.0-rc.5...v1.0.0-rc.6) (2026-06-25)

### Features

* **jobs:** batch Telegram messages per chat ([2324b58](https://github.com/disafronov/skilled/commit/2324b5853762e8bb0160dc100e0891004281ce86))

### Bug Fixes

* **jobs:** join batched Telegram messages with spaces ([1abce24](https://github.com/disafronov/skilled/commit/1abce2497a3e4a1d534a756c55279160bccc7a47))

## [1.0.0-rc.5](https://github.com/disafronov/skilled/compare/v1.0.0-rc.4...v1.0.0-rc.5) (2026-06-25)

### Features

* redirect to admin ([7c0c4fc](https://github.com/disafronov/skilled/commit/7c0c4fc06a4dc84915b60f70a00ae89a2173a2d6))

## [1.0.0-rc.4](https://github.com/disafronov/skilled/compare/v1.0.0-rc.3...v1.0.0-rc.4) (2026-06-25)

### Features

* **health:** add health check endpoints ([6450939](https://github.com/disafronov/skilled/commit/6450939ad70879c5706b12d2fb118f2bda720774))

### Bug Fixes

* **jobs:** remove cron schedules ([595446f](https://github.com/disafronov/skilled/commit/595446f068fde3b48afaab14b0ba8e82f6c2c638))

## [1.0.0-rc.3](https://github.com/disafronov/skilled/compare/v1.0.0-rc.2...v1.0.0-rc.3) (2026-06-25)

### Bug Fixes

* static ([a945b1f](https://github.com/disafronov/skilled/commit/a945b1f0185db748682c4305dd59806f06f266a4))

## [1.0.0-rc.2](https://github.com/disafronov/skilled/compare/v1.0.0-rc.1...v1.0.0-rc.2) (2026-06-25)

### Bug Fixes

* settings ([e932f48](https://github.com/disafronov/skilled/commit/e932f480aafc44fc0848c023257d02498766bb69))
* settings ([a11ede1](https://github.com/disafronov/skilled/commit/a11ede1a3bd9d0090780e413d31bf4ca01beb02f))

## 1.0.0-rc.1 (2026-06-25)

### Features

* cron ([4048ec3](https://github.com/disafronov/skilled/commit/4048ec3b3e3b56d4a49b2b2a25aa9d73d3351642))
* initial ([1b64717](https://github.com/disafronov/skilled/commit/1b64717f84de7d0a99d15957adb2479ab78080fe))
* **llm:** load global policy from file ([b3ee07e](https://github.com/disafronov/skilled/commit/b3ee07e2afbb42bcf7ba2daa6b741839bf3dc823))
* **telegram:** acknowledge queueing and reply with results ([a194046](https://github.com/disafronov/skilled/commit/a194046d2ce494b862e8e587f4561c6745afe244))
* update ([a6f4136](https://github.com/disafronov/skilled/commit/a6f4136d0f778fa7b0e7d2c30f0350a7f6dbed9d))
* update ([04517c2](https://github.com/disafronov/skilled/commit/04517c274244ddb57c140e35125ea2f91701bb85))

### Bug Fixes

* add typing to q2 operational code ([9c74077](https://github.com/disafronov/skilled/commit/9c74077b1b7bcb52be2185d269d6d4e9e5f5c2cf))
* explicit httpx timeouts + error handling + atomic offset persistence ([930c5fc](https://github.com/disafronov/skilled/commit/930c5fc3056704a9c8455dfbfd1a89dfa4f5f4f8))
* harden q2 scheduling and telegram delivery ([e1352bc](https://github.com/disafronov/skilled/commit/e1352bc0c46a716443c330af5a28f06ab6542f24))
* **jobs:** refresh audit timestamps on state updates ([2b87c16](https://github.com/disafronov/skilled/commit/2b87c16d696606be1196853b91223ae49bdacd2d))
* **scheduler:** enforce managed q2 schedules ([44754bf](https://github.com/disafronov/skilled/commit/44754bfa289250b49316ff91ab1e251258c3bf8c))
* silence flake8 in telegram markdown sanitization ([e431a37](https://github.com/disafronov/skilled/commit/e431a376778c7460f9dd471191bfd8aa0ef2b681))
* tasks ([a6561a4](https://github.com/disafronov/skilled/commit/a6561a47a1fcfa070dded17e7b3b8fe2822bd603))
* **telegram:** surface api error response bodies ([b5a1d9e](https://github.com/disafronov/skilled/commit/b5a1d9e88e5f1572d7758ff31a164d9e850c10d1))
* use standard cron schedule expressions ([b94f98c](https://github.com/disafronov/skilled/commit/b94f98c03c29ba8f352731a3d93b29d2cb417d6d))
