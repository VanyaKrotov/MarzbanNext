# Agent instructions

## Product context

Read [PRODUCT.md](PRODUCT.md) before forming implementation plans, proposing solutions, designing interfaces, writing code, or drafting interface copy, documentation, and other product materials. Ground the work in the product's audience, core scenarios, terminology, capabilities, and constraints.

- Relate proposed changes to the user task they serve and preserve the documented product behavior unless the requested change alters it.
- Check concrete behavior against the relevant code and feature documentation. Keep implemented capabilities distinct from proposals and assumptions; reference specifications for other products are not evidence that a feature is implemented in MarzbanNext.
- Update the product description when a delivered change alters its facts. Ask for clarification when a missing product decision materially affects the solution.

## Interface language

- Treat interface text as a connected system. Before adding or changing copy, inspect related screens and existing translation keys, and align titles, field labels, buttons, hints, validation, confirmations, empty states, and success messages within the same flow.
- Use one canonical term for each product entity, action, and state within each locale. Follow the terminology in `PRODUCT.md` and established interface wording; avoid synonyms that make the same concept appear to be different features.
- Use simple, familiar words, short sentences, and direct action labels. Keep grammar, tone, capitalization, and punctuation consistent within each locale.
- Keep visible button labels as compact as the surrounding context allows. In a dialog or section that already identifies the entity, use the action alone: "Create", "Save", "Delete", "Add", or "Connect". Do not repeat the entity or "changes" in submit buttons. Keep entity names in headings and in action labels where they are needed to distinguish choices. Preserve descriptive accessible names for icon-only controls, and use "Create" for creation and "Save" for editing consistently across locales.
- Describe the actual action, result, or condition precisely. Preserve meaningful distinctions such as disabling versus deleting, and a subscription template versus generator settings. Do not promise behavior the product does not provide.
- Include only information needed to understand the current state, complete the task, or make an informed decision. Remove redundant explanations, repeated context, filler, and unnecessary qualifications.
- Explain technical details only when they help the user make a decision. Preserve necessary consequences, limits, units, and recovery steps rather than shortening copy at the expense of accuracy.
- Reuse existing translation keys when their meaning matches. When terminology changes, update the related strings in the affected flow and all supported locales, preserving the same meaning with natural phrasing in each language.
- Review changed copy in context before finishing: the entity and action should be clear, related messages should agree, and each sentence should add useful information.

## Selecting skills

Before implementing a change, read the `SKILL.md` files relevant to the task. Use their supporting references only as needed. Select skills by the behavior being changed; do not load every skill for every task.

### Project guidance

| Task | Skill |
| --- | --- |
| Architecture, runtime flow, or unfamiliar project areas | [marzban-project-overview](.agents/skills/marzban-project-overview/SKILL.md) |
| Dashboard components, forms, routing, state, API integration, or translations | [marzban-dashboard-change](.agents/skills/marzban-dashboard-change/SKILL.md) |
| REST endpoints, request/response models, or authorization | [marzban-add-endpoint](.agents/skills/marzban-add-endpoint/SKILL.md) |
| Database models, CRUD, or Alembic migrations | [marzban-update-db](.agents/skills/marzban-update-db/SKILL.md) |
| Xray configuration, subscriptions, nodes, or synchronization | [marzban-xray-change](.agents/skills/marzban-xray-change/SKILL.md) |
| Behavior-preserving Python or TypeScript refactoring | [marzban-refactoring](.agents/skills/marzban-refactoring/SKILL.md) |

### Frontend and design guidance

| Task | Skill |
| --- | --- |
| Writing, reviewing, or refactoring React components; data fetching, rendering, or bundle performance | [vercel-react-best-practices](.agents/skills/vercel-react-best-practices/SKILL.md) |
| Designing or changing pages, layouts, forms, interactions, responsive behavior, accessibility, typography, or colors | [ui-ux-pro-max](.agents/skills/ui-ux-pro-max/SKILL.md) |
| Reviewing UI code for accessibility, usability, or Web Interface Guidelines compliance | [web-design-guidelines](.agents/skills/web-design-guidelines/SKILL.md) |
| Working with shadcn primitives, component composition, or registries | [shadcn](.agents/skills/shadcn/SKILL.md) |

## Applying skill guidance

- Combine the dashboard skill with the relevant React or design skills when a frontend task crosses those concerns.
- Project-specific conventions take precedence over general skill recommendations. Preserve the existing React 18, TypeScript, Vite, Tailwind, shadcn, Zustand, TanStack Query, react-hook-form, Zod, i18next, and shared Axios architecture.
- Apply React guidance that fits this application. Next.js, server component, and SSR examples do not justify changing the framework or introducing unsupported APIs.
- Reuse existing components and design tokens. Add missing shadcn primitives through the project's `npm.cmd run ui:add -- <component...>` wrapper from `app/dashboard`.
- When using `web-design-guidelines` for a review, fetch the current guidelines from the source specified in that skill and review the files relevant to the task.
- Keep design and performance changes within the requested scope. Use the verification steps in the applicable project skill.
