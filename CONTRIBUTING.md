# Contributing

Thanks for helping. The project is built so that people can work on different apps without stepping on each other.

## Ground rules

1. **Contracts first.** Before an app sends or accepts a new message, the message is described in `contracts/` (schema + example) and reviewed. Apps never call each other in ways that are not in a contract.
2. **One app, one folder.** Code for an app lives only in its folder under `apps/`. Apps may use any language or framework, as long as they speak the contracts.
3. **Spec first, then our choice.** If the ECB documents define a field, we use their name and meaning. Where they are silent or contradict each other, we make one choice and record it in `contracts/INTERPRETATION.md` with the page reference.
4. **Mark placeholders.** Anything invented because the spec is missing (e.g. onboarding calls, reason codes) is marked `placeholder` in the schema description and in the example.
5. **No real data.** Only fictional people, banks and account numbers.

## License

By contributing you agree that your contribution is published under the [MIT license](LICENSE).

## Making a change to a contract

- Open a pull request that changes the schema, the examples and, if needed, `INTERPRETATION.md` together.
- Run `python3 tools/generate_examples.py` and `python3 tools/validate.py`. Both must pass.
- Breaking changes bump the contract version in `contracts/README.md`.

## Decisions

Bigger decisions are written down as short ADRs in `docs/decisions/`. If you disagree with one, open an issue rather than working around it.
