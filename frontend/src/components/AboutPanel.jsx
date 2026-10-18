import React from 'react'
import { Icon } from './Icons.jsx'

export default function AboutPanel({ onBack }) {
  return (
    <section className="about-view">
      <div className="about-view__hero">
        <div className="about-view__mark"><img src="/logo.png" alt="Умный поиск" /></div>
        <div>
          <span className="eyebrow">Открытый MVP · SetRetail10</span>
          <h1>Умный поиск</h1>
          <p>Задавайте вопросы о SetRetail10 без регистрации. Поиск использует публичную документацию Crystal Service и показывает ссылки на найденные материалы.</p>
          <button type="button" className="primary-button" onClick={onBack}>Вернуться в чат</button>
        </div>
      </div>

      <div className="about-grid">
        <article>
          <Icon name="file" size={24} />
          <h3>База знаний SetRetail10</h3>
          <p><a href="https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/overview" target="_blank" rel="noopener noreferrer">Открыть исходную документацию ↗</a></p>
        </article>
        <article>
          <Icon name="sparkles" size={24} />
          <h3>Локальный AI</h3>
          <p>Qwen формирует ответ по найденным материалам. MVP может ошибаться — сверяйте важные детали с источниками.</p>
        </article>
        <article>
          <Icon name="shield" size={24} />
          <h3>Проверяемый ответ</h3>
          <p>Каждый успешный ответ сопровождается ссылками на использованные источники.</p>
        </article>
      </div>
    </section>
  )
}
