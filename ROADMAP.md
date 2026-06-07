# Dronefly Architectural Roadmap

We're in the middle of a long-term project to transform Dronefly from a *Red DiscordBot Cog for iNaturalist users* into a standalone *Application Framework* for making command-driven apps to rapidly access personal and global biodiversity data in concise, interactive displays well-suited to being used on chat platforms. It will continue to be primarily for *Discord* users to access *iNaturalist* data, but we envision other ports and data providers being supported in future.

This builds on earlier work to separate out a `dronefly-core` layer starting in October 2021, and a `dronefly-discord` layer starting in 2023, supplemented by `dronefly-cli` at the same time to help us model changes to the Discord commands and construct new, cleaner commands without Discord dependencies. Currently, we have reached a point where, while we already have a significant amount of working code in production, several of our architectural decisions made over this period of time seem to not hold up well under scrutiny. Therefore, in the latter half of 2026, we'll be engaged in further architectural changes and hope to have enough in place so that in 2027 we will be on the home stretch to finishing the whole job.

---

## Core Philosophy

1. **Strict Isolation:** `dronefly-core` must remain entirely ignorant of Discord, `discord.py`, and the Red Bot framework.
2. **Domain Entities:** Use domain models to represent data, including the `Workspace` entity to abstract servers/guilds.
3. **The UI Triad:** UI interactions follow a strict pattern: **Data Source** (State), **Formatter** (Presentation), and **View/Menu** (Interaction).
4. **Configuration as a Service:** Configuration is abstracted behind a `SettingsProvider` accessed via `Workspace` entities, decoupling the application from specific file formats or bot-framwork configs.

---

## The Core Concept: The "Workspace" Abstraction

* **`Workspace`:** A `dronefly-core` entity representing a logical container (e.g., a Guild, a CLI session, or a Web Dashboard).
* **Encapsulation:** The `Workspace` model owns the logic for resolving place aliases, project aliases, event project settings, and user mappings.
* **Abstraction:** The `Discord Cog` or `CLI` simply passes an ID to the `Core`, which returns a `Workspace` object. The UI interacts with a unified configuration interface; it does not know or care if the underlying settings are retrieved from a local TOML file, an export file, or a future remote API.

---

## Migration Plan

This plan addresses problems with our efforts to migrate code out of the `Discord Cog` down into `Core` and then rework the cog to use it. We have often tackled too many changes at once and made too many ad-hoc decisions which we later regretted. Therefore, in the next several months we're proceeding more slowly with a series of smaller, more focused PRs. We'll use the simple `user` command as our model command to achieve `Discord` / `Core` separation, then stop and consider if the archetictural roadmap needs any further adjustments to tackle the remaining command migrations.

### Phase 1: Foundations (Core)

* **Define `Workspace` Entity:** Create the domain model in `dronefly-core` to encapsulate server-specific logic.
* **Implement `UserProfileResult`:** Define the domain model inheriting from `pyinaturalist.models.BaseModel`.
* **Establish `ConfigService`:** Centralize `config.toml` parsing into a service that populates `Workspace` attributes.

### Phase 2: The "Tracer Bullet" (User Command Rewrite)

* **PR 1 (Core Logic):** Add the `UserCommand.execute()` method to `dronefly-core`. It fetches raw data and hydrates the `UserProfileResult`, augmented by the current `Workspace` data.
* **PR 2 (CLI Update):** Update the CLI to use the new `Workspace` and `UserProfileResult` objects.
* **PR 3 (Discord Formatter):** Create a stateless function in `discord` that transforms `UserProfileResult` into a `discord.Embed`.
* **PR 4 (Discord Port):** Simplify the `[p]user` cog into a thin "Traffic Cop" that requests a `Workspace` from the Core and delegates formatting to the new utility.

### Phase 3: Total Decoupling

* **Migrate Legacy Data:** Migrate Legacy Data: Gradually move all remaining server-specific configurations into the standardized `config.toml` configuration provider, ensuring all settings are accessible through the `Workspace` abstraction.
* **Remove Red Dependencies:** Delete remaining references to Red’s `Config` within the cogs, finalizing the migration to the `Workspace` abstraction.

---

## Action Item Checklist

* [ ] Define `Workspace` in `dronefly-core`.
* [ ] Define `UserProfileResult` (Inheriting from `BaseModel`).
* [ ] Create `ConfigService` in `dronefly-core`.
* [ ] Develop stateless formatter in `dronefly-discord`.
* [ ] Implement "Traffic Cop" in the Discord Cog.
