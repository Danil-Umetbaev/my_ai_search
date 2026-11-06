import React from 'react'
import { Icon } from './Icons.jsx'

export default function AboutPanel({ onBack }) {
  return (
    <section className="about-view">
      <div className="about-view__hero">
        <div className="about-view__mark"><img src="/logo.png" alt="Умный поиск" /></div>
        <div>
          <span className="eyebrow">Помощник по кассовому оборудованию</span>
          <h1>Умный поиск</h1>
          <p>Задавайте вопросы о Вики Принт, Пирит 2Ф и АТОЛ FPrint-22ПТК. Поиск использует инструкции производителей и показывает источники ответа.</p>
          <button type="button" className="primary-button" onClick={onBack}>Вернуться в чат</button>
        </div>
      </div>

      <div className="about-grid">
        <article>
          <Icon name="file" size={24} />
          <h3>Источники</h3>
          <p><a href="https://help.dreamkas.ru/kb/viki-printy/" target="_blank" rel="noopener noreferrer">Вики Принт ↗</a></p>
        <p><a href="/api/v1/knowledge-assets/pirit-2f-manual.pdf" target="_blank" rel="noopener noreferrer">Руководство Пирит 2Ф ↗</a></p>
          <p><a href="/api/v1/knowledge-assets/cc17e6a85892bc06be4ecc1f707b398fab27f7c58db081588c176f456815bb40.pdf" target="_blank" rel="noopener noreferrer">Руководство АТОЛ FPrint-22ПТК ↗</a></p>
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
