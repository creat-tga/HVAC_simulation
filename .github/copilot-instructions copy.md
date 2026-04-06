# Copilot Instructions

# 强制交互协议

## 所有的交流过程请使用中文，即使我发送英文给你，除非我明确要求你使用英文回答

## 核心规则：每次回复结束前必须调用 `ask_user` 工具

这是不可跳过的强制协议。在你的每一轮回复中，你必须执行以下操作之一：

1. **完成用户请求后** → 立即调用 `ask_user` 工具，提出与当前上下文相关的后续问题
2. **存在任何不确定性时** → 不要猜测执行，立即调用 `ask_user` 工具进行澄清

## 禁止行为

- **禁止在不调用 `ask_user` 的情况下结束回复**
- **禁止使用终结性表达**（如"希望对你有帮助"、"如有问题随时提问"等）
- **禁止猜测用户意图** — 不确定就用 `ask_user` 询问

## `ask_user` 调用要求

- 问题必须与当前任务上下文直接相关
- 问题必须具体、可操作，不要问泛泛的"还需要什么帮助"
- 可以提供选项供用户选择，降低用户输入成本
- 必须要有用户自定义输入的选项


This file provides context and instructions for GitHub Copilot to work effectively in the `HVAC_simulation` project.

## Project Overview

**HVAC_simulation** is a platform for simulating HVAC systems, including building load simulation (via EnergyPlus) and system energy consumption analysis (chillers, heat pumps, etc.).

### Tech Stack
-   **Frontend**: Vue 3 (Composition API), TypeScript, Vite
-   **Backend**: Python 3.12, FastAPI, Uvicorn
-   **Package Managers**: `pnpm` (Frontend), `uv` (Backend)
-   **Simulation**: EnergyPlus integration

## Build, Test, and Run Commands

### Frontend (`/frontend` or similar directory)
*   **Install Dependencies**: `pnpm install`
*   **Start Dev Server**: `pnpm run dev`
*   **Build for Production**: `pnpm run build`
*   **Lint Code**: `pnpm run lint`
*   **Run Unit Tests**: `pnpm run test:unit` (if available)

### Backend (`/backend` or similar directory)
*   **Install Dependencies**: `uv sync`
*   **Run Dev Server**: `uv run uvicorn main:app --reload`
*   **Run Tests**: `uv run pytest`
*   **Add Dependency**: `uv add <package_name>`

## High-Level Architecture

1.  **Frontend**: Uses Vue 3 with Composition API and TypeScript. Components should be modular and reusable. State management likely via Pinia (standard for Vue 3).
2.  **Backend**: Exposes HTTP APIs using FastAPI.
3.  **Simulation Engine**:
    -   **Load Simulation**: Wraps EnergyPlus calls.
    -   **System Simulation**: Python-based models for HVAC components (chillers, pumps, towers).
4.  **Data**: Simulation results are generated as reports (energy, cost, carbon).

## Key Conventions

### General
-   **Language**: Use **English** for code/comments and **Chinese** for documentation/reports (as per `plan.md` context).
-   **Path Separators**: Use forward slashes `/` in code for cross-platform compatibility, but be aware of Windows backslashes `\` in shell paths.

### Frontend (Vue/TS)
-   Use **Composition API** (`<script setup lang="ts">`) for all components.
-   Ensure strict **TypeScript** typing; avoid `any`.
-   Use `pnpm` exclusively for package management.

### Backend (Python)
-   Use **Python 3.12+** features (type hinting, f-strings).
-   Manage virtual environments and dependencies via **uv**.
-   Follow **PEP 8** style guidelines.
-   API endpoints should be async where appropriate (`async def`).

### Simulation Logic
-   EnergyPlus integration should handle input/output files securely.
-   Modularize system components (e.g., `Chiller`, `Boiler` classes) for flexibility.
