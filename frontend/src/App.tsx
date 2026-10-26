import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api } from "./api";
import type {
  ChatMessage,
  AssistantConversation,
  Client,
  CreditApplication,
  Need,
  NeedTag,
  Recommendation,
  View,
} from "./types";

const ASSETS = "/assets";

const PURPOSES: Array<{ value: NeedTag; label: string }> = [
  { value: "investment", label: "Покупка оборудования" },
  { value: "working_capital", label: "Оборотные средства" },
  { value: "cash_gap", label: "Кассовый разрыв" },
  { value: "vehicle", label: "Транспорт" },
  { value: "real_estate", label: "Недвижимость" },
  { value: "refinancing", label: "Рефинансирование" },
  { value: "tender", label: "Тендер" },
  { value: "any", label: "Любые бизнес-цели" },
];

const CLIENT_META: Record<string, { activity: string; registered: string; ogrn: string; phone: string }> = {
  demo_cafe: {
    activity: "Общественное питание",
    registered: "15.01.2024",
    ogrn: "324770000101950",
    phone: "+7 987 234 67 82",
  },
  demo_logistics: {
    activity: "Грузовые перевозки",
    registered: "11.10.2022",
    ogrn: "1227700201003",
    phone: "+7 905 455 24 10",
  },
  demo_newbie: {
    activity: "Интернет-магазин",
    registered: "18.05.2026",
    ogrn: "326770030100210",
    phone: "+7 916 300 10 21",
  },
};

const fallbackMeta = {
  activity: "Предпринимательская деятельность",
  registered: "12.03.2023",
  ogrn: "1281919432473",
  phone: "+7 987 234 67 82",
};

function money(value: number | null | undefined) {
  if (value == null) return "—";
  return `${Math.round(value).toLocaleString("ru-RU")} ₽`;
}

function percent(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}%`;
}

function snapshotNumber(value: unknown) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function term(value: number | null | undefined) {
  if (!value) return "—";
  if (value % 12 === 0) {
    const years = value / 12;
    return `${years} ${years === 1 ? "год" : years < 5 ? "года" : "лет"}`;
  }
  return `${value} мес.`;
}

function purposeLabel(value: NeedTag | null | undefined) {
  return PURPOSES.find((item) => item.value === value)?.label || "Развитие бизнеса";
}

function clientMeta(client: Client | null) {
  if (!client) return fallbackMeta;
  const preset = CLIENT_META[client.id];
  let saved: typeof fallbackMeta | null = null;
  try {
    saved = JSON.parse(localStorage.getItem(`alfa-client-meta:${client.id}`) || "null") as typeof fallbackMeta | null;
  } catch {
    // Профиль остаётся работоспособным даже при повреждённом localStorage.
  }
  return {
    activity: saved?.activity || preset?.activity || client.okved || fallbackMeta.activity,
    registered: client.registration_date || saved?.registered || preset?.registered || fallbackMeta.registered,
    ogrn: client.ogrn || saved?.ogrn || preset?.ogrn || fallbackMeta.ogrn,
    phone: client.phone || saved?.phone || preset?.phone || fallbackMeta.phone,
  };
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ children, ...props }) => <a {...props} target="_blank" rel="noreferrer">{children}</a>,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function CloseButton({ onClick, label = "Закрыть" }: { onClick: () => void; label?: string }) {
  return (
    <button className="close-button" onClick={onClick} aria-label={label} type="button">
      <img src={`${ASSETS}/close.svg`} alt="" />
    </button>
  );
}

function Field({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`display-field${wide ? " display-field--wide" : ""}`}>
      <span>{label}</span>
      <strong>{value || "—"}</strong>
    </div>
  );
}

function EditableField({
  label,
  value,
  onChange,
  type = "text",
  min,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  min?: number;
}) {
  const numeric = type === "number";
  const [draft, setDraft] = useState(String(value));

  useEffect(() => setDraft(String(value)), [value]);

  function change(next: string) {
    if (numeric && !/^\d*(?:[.,]\d*)?$/.test(next.replaceAll(" ", ""))) return;
    setDraft(next);
    if (next.trim() !== "") onChange(next.replaceAll(" ", "").replace(",", "."));
  }

  function blur() {
    if (!numeric) return;
    if (draft.trim() === "") {
      setDraft(String(value));
      return;
    }
    const parsed = Number(draft.replaceAll(" ", "").replace(",", "."));
    const normalized = min == null ? parsed : Math.max(min, parsed);
    setDraft(String(normalized));
    onChange(String(normalized));
  }

  return (
    <label className="display-field display-field--editable">
      <span>{label}</span>
      <input
        type="text"
        inputMode={numeric ? "decimal" : undefined}
        value={draft}
        onChange={(event) => change(event.target.value)}
        onBlur={blur}
      />
    </label>
  );
}

function PrimaryButton({ children, onClick, disabled = false, type = "button", className = "" }: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  return (
    <button className={`primary-button ${className}`} onClick={onClick} disabled={disabled} type={type}>
      {children}
    </button>
  );
}

function Navigation({ view, assistantOpen, onNavigate, onAssistant }: {
  view: View;
  assistantOpen: boolean;
  onNavigate: (view: View) => void;
  onAssistant: () => void;
}) {
  const active = assistantOpen
    ? "assistant"
    : view === "dashboard"
      ? "dashboard"
      : view === "applications"
        ? "applications"
        : "home";
  return (
    <nav className={`app-navigation${view === "home" ? " app-navigation--home" : ""}`} aria-label="Основная навигация">
      <button className={active === "home" ? "active" : ""} onClick={() => onNavigate("home")}>главная</button>
      <button className={active === "assistant" ? "active" : ""} onClick={onAssistant}>ИИ-чат</button>
      <button className={active === "dashboard" ? "active" : ""} onClick={() => onNavigate("dashboard")}>личный кабинет</button>
      <button className={active === "applications" ? "active" : ""} onClick={() => onNavigate("applications")}>заявки</button>
    </nav>
  );
}

function ApplicationsScreen({ applications, productNames, onOpen, onClose }: {
  applications: CreditApplication[];
  productNames: Record<string, string>;
  onOpen: (application: CreditApplication) => void;
  onClose: () => void;
}) {
  return (
    <main className="screen centered-screen">
      <section className="applications-card">
        <CloseButton onClick={onClose} />
        <h1>Заявки на кредит</h1>
        {applications.length === 0 ? (
          <p className="applications-empty">Заявок нет</p>
        ) : (
          <div className="applications-list">
            {applications.map((application, index) => (
              <article className="application-row" key={application.id}>
                <div>
                  <span>Заявка {index + 1}</span>
                  <strong>{String(application.credit_snapshot?.product_name || productNames[application.product_id || ""] || application.product_id || "Кредитная заявка")}</strong>
                </div>
                <button className="text-link" onClick={() => onOpen(application)}>Открыть заявку</button>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function HomeScreen({ client, onFinance }: {
  client: Client | null;
  onFinance: () => void;
}) {
  const [revealed, setRevealed] = useState(false);
  const meta = clientMeta(client);
  const firstName = client?.owner_name?.split(" ")[1] || "Егор";

  useEffect(() => {
    const frame = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <main className="screen home-screen">
      <section className={`home-card${revealed ? " home-card--revealed" : ""}`}>
        <div className="home-copy">
          <h1>Добрый день, {firstName}</h1>
          <h2>{client?.name || "Ваш бизнес"}</h2>
          <p>
            ИНН {client?.inn || "—"}<br />
            ОГРН {meta.ogrn}<br />
            {meta.registered}<br />
            {meta.activity}
          </p>
          <PrimaryButton onClick={onFinance}>Получить финансирование</PrimaryButton>
        </div>
        <img className="home-illustration" src={`${ASSETS}/main-business.png`} alt="Финансирование бизнеса" />
      </section>
    </main>
  );
}

function LoginScreen({ clients, selectedClient, onLogin, onRegister }: {
  clients: Client[];
  selectedClient: Client | null;
  onLogin: (client: Client) => void;
  onRegister: () => void;
}) {
  const [inn, setInn] = useState("");
  const [ogrn, setOgrn] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!selectedClient) return;
    setInn(selectedClient.inn);
    setOgrn(clientMeta(selectedClient).ogrn);
    setMessage("");
  }, [selectedClient]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const client = clients.find((item) => item.inn === inn.trim());
    if (!client || clientMeta(client).ogrn !== ogrn.trim()) {
      setMessage("Клиент с такими ИНН и ОГРН не найден");
      return;
    }
    onLogin(client);
  }

  return (
    <main className="screen centered-screen">
      <form className="auth-card auth-card--login" onSubmit={submit}>
        <h1>Вход</h1>
        <EditableField label="ИНН" value={inn} onChange={setInn} />
        <EditableField label="ОГРН" value={ogrn} onChange={setOgrn} />
        {message && <p className="form-error">{message}</p>}
        <PrimaryButton type="submit">Войти</PrimaryButton>
        <button className="text-link" type="button" onClick={onRegister}>Регистрация</button>
      </form>
    </main>
  );
}

function RegisterScreen({ onDone, onClose }: {
  onDone: (client: Client, meta: typeof fallbackMeta) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    owner: "Шипилов Егор Павлович",
    company: "ООО «ВЕКТОР»",
    activity: "Строительные услуги",
    inn: "1281381832",
    ogrn: "1281919432473",
    date: "12.03.2023",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (key: keyof typeof form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const registered = await api.register({
        owner_name: form.owner.trim(),
        name: form.company.trim(),
        activity: form.activity.trim(),
        inn: form.inn.trim(),
        ogrn: form.ogrn.trim(),
        registration_date: form.date.trim(),
        legal_form: form.inn.trim().length === 12 ? "ip" : "ooo",
      });
      onDone(registered, {
        activity: form.activity.trim(),
        registered: form.date.trim(),
        ogrn: form.ogrn.trim(),
        phone: fallbackMeta.phone,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось зарегистрировать кабинет");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen centered-screen">
      <form className="auth-card auth-card--register" onSubmit={submit}>
        <CloseButton onClick={onClose} />
        <h1>Регистрация</h1>
        <div className="form-grid">
          <EditableField label="ФИО" value={form.owner} onChange={update("owner")} />
          <EditableField label="ИНН" value={form.inn} onChange={update("inn")} />
          <EditableField label="Название компании" value={form.company} onChange={update("company")} />
          <EditableField label="ОГРН" value={form.ogrn} onChange={update("ogrn")} />
          <EditableField label="Вид деятельности" value={form.activity} onChange={update("activity")} />
          <EditableField label="Дата регистрации" value={form.date} onChange={update("date")} />
        </div>
        {error && <p className="form-error register-error">{error}</p>}
        <PrimaryButton disabled={busy} type="submit" className="register-submit">{busy ? "Регистрируем…" : "Зарегистрироваться"}</PrimaryButton>
      </form>
    </main>
  );
}

function DashboardScreen({ client, applications, onNew, onApplications }: {
  client: Client;
  applications: CreditApplication[];
  onNew: () => void;
  onApplications: () => void;
}) {
  const meta = clientMeta(client);
  return (
    <main className="screen centered-screen">
      <section className="cabinet-card">
        <div className="cabinet-title">
          <img src={`${ASSETS}/user.svg`} alt="" />
          <h1>Личный кабинет</h1>
        </div>
        <div className="profile-grid">
          <Field label="ФИО" value={client.owner_name} />
          <Field label="ИНН" value={client.inn} />
          <Field label="Название компании" value={client.name} />
          <Field label="ОГРН" value={meta.ogrn} />
          <Field label="Вид деятельности" value={meta.activity} />
          <Field label="Дата регистрации" value={meta.registered} />
        </div>
        <PrimaryButton className="cabinet-action" onClick={onApplications}>Отслеживать заявки кредитов</PrimaryButton>
        <button className="new-application-button" onClick={onNew}>Подать новую заявку</button>
      </section>
    </main>
  );
}

function CreditWizard({ initial, onSubmit, busy }: {
  initial: Need;
  onSubmit: (need: Need) => void;
  busy: boolean;
}) {
  const [need, setNeed] = useState(initial);
  const [established, setEstablished] = useState(true);
  return (
    <main className="screen centered-screen">
      <section className="wizard-shell">
        <div className="wizard-hero">
          <h1>Подберем<br />для вас<br />кредит</h1>
          <img src={`${ASSETS}/analytics.png`} alt="Аналитика кредитования" />
        </div>
        <form className="wizard-form" onSubmit={(event) => { event.preventDefault(); onSubmit(need); }}>
          <div className="wizard-inner">
            <h2>Параметры кредита</h2>
            <span className="control-label">Залог</span>
            <div className="segmented">
              <button type="button" className={!need.collateral ? "active" : ""} onClick={() => setNeed({ ...need, collateral: false })}>Без залога</button>
              <button type="button" className={need.collateral ? "active" : ""} onClick={() => setNeed({ ...need, collateral: true })}>С залогом</button>
            </div>
            <span className="control-label">Срок ведения бизнеса</span>
            <div className="segmented">
              <button type="button" className={!established ? "active" : ""} onClick={() => setEstablished(false)}>До 9 месяцев</button>
              <button type="button" className={established ? "active" : ""} onClick={() => setEstablished(true)}>Более 9 месяцев</button>
            </div>
            <div className="wizard-values">
              <EditableField label="Желаемая сумма кредита" value={need.amount} type="number" min={10000} onChange={(value) => setNeed({ ...need, amount: Number(value) })} />
              <EditableField label="Срок кредита, месяцев" value={need.term_months} type="number" min={1} onChange={(value) => setNeed({ ...need, term_months: Number(value) })} />
              <label className="display-field display-field--editable display-field--wide">
                <span>Цель финансирования</span>
                <select value={need.purpose} onChange={(event) => setNeed({ ...need, purpose: event.target.value as NeedTag })}>
                  {PURPOSES.map((purpose) => <option value={purpose.value} key={purpose.value}>{purpose.label}</option>)}
                </select>
              </label>
            </div>
          </div>
          <PrimaryButton type="submit" disabled={busy} className="wizard-submit">{busy ? "Подбираем…" : "Подобрать"}</PrimaryButton>
        </form>
      </section>
    </main>
  );
}

function ProductMetrics({ item }: { item: Recommendation }) {
  return (
    <div className="product-metrics">
      <div><span>Ставка</span><strong>{percent(item.rate)}</strong></div>
      <div><span>Переплата</span><strong>{money(item.overpayment)}</strong></div>
      <div><span>Платеж</span><strong>{money(item.monthly_payment)}</strong></div>
    </div>
  );
}

function ProductCard({ item, purpose, expanded, onDetails, onApply }: {
  item: Recommendation;
  purpose: NeedTag;
  expanded?: boolean;
  onDetails: () => void;
  onApply: () => void;
}) {
  return (
    <article className={`product-card${expanded ? " product-card--expanded" : ""}`}>
      <h2>{item.name}</h2>
      <h3>{purposeLabel(purpose)}</h3>
      <ProductMetrics item={item} />
      {expanded && (
        <ul className="product-conditions">
          <li>Сумма: до {money(item.max_amount || item.amount)}</li>
          <li>Срок: {term(item.term_months)}</li>
          <li>Ставка: от {percent(item.rate)} годовых</li>
          <li>{item.warnings.length ? item.warnings[0] : "Индивидуальные условия по профилю бизнеса"}</li>
          {item.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      )}
      <div className="product-actions">
        <button className="secondary-button" onClick={onDetails}>{expanded ? "Свернуть" : "Подробнее"}</button>
        <PrimaryButton onClick={onApply}>Оформить</PrimaryButton>
      </div>
    </article>
  );
}

function ChatPanel({ clientId, need, product, expanded }: {
  clientId: string;
  need: Need;
  product: Recommendation | null;
  expanded: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadId = useRef(crypto.randomUUID());
  const explainedProduct = useRef<string | null>(null);

  async function send(text = input, visibleText = text) {
    const value = text.trim();
    if (!value || busy) return;
    setMessages((current) => [...current, { role: "user", content: visibleText }]);
    setInput("");
    setBusy(true);
    try {
      const result = await api.chat(clientId, threadId.current, value);
      setMessages((current) => [...current, { role: "assistant", content: result.response }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", content: error instanceof Error ? error.message : "Ассистент временно недоступен" }]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!expanded || !product || explainedProduct.current === product.product_id) return;
    explainedProduct.current = product.product_id;
    const context = [
      "Объясни условия выбранного кредита простым языком.",
      "Не спрашивай повторно продукт, цель, сумму, срок или наличие залога: эти данные уже переданы ниже.",
      `Продукт: ${product.name}.`,
      `Цель: ${purposeLabel(need.purpose)}.`,
      `Запрошенная сумма: ${money(need.amount)}.`,
      `Срок: ${term(need.term_months)}.`,
      `Залог: ${need.collateral ? "есть" : "нет"}.`,
      `Ставка: ${percent(product.rate)}.`,
      `Ежемесячный платёж: ${money(product.monthly_payment)}.`,
      `Переплата: ${money(product.overpayment)}.`,
      `Максимальная сумма продукта: ${money(product.max_amount)}.`,
      `Причины рекомендации: ${product.reasons.join("; ") || "не указаны"}.`,
      `Предупреждения: ${product.warnings.join("; ") || "нет"}.`,
      "Объясни ставку, платёж, переплату, срок, ограничения и почему продукт подходит. Не придумывай отсутствующие условия.",
    ].join("\n");
    void send(context, "Объясни условия простым языком");
  }, [expanded, product?.product_id]);

  return (
    <section className="chat-panel">
      <div className="chat-scroll">
        <div className="loan-summary">
          <h2>Параметры кредита</h2>
          <p>{need.collateral ? "С залогом" : "Без залога"}</p>
          <p>{term(need.term_months)}</p>
          <p>{money(need.amount)}</p>
          <p>{purposeLabel(need.purpose)}</p>
        </div>
        <div className="chat-messages">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-bubble chat-bubble--${message.role}`}>
              <MarkdownMessage content={message.content} />
            </div>
          ))}
          {busy && <div className="chat-bubble chat-bubble--assistant">Формирую ответ…</div>}
        </div>
      </div>
      <form className="chat-input" onSubmit={(event) => { event.preventDefault(); void send(); }}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Введите запрос" />
        <button aria-label="Отправить" type="submit"><img src={`${ASSETS}/arrow.svg`} alt="" /></button>
      </form>
    </section>
  );
}

function RecommendationsScreen({ recommendations, need, clientId, selected, details, onSelect, onApply }: {
  recommendations: Recommendation[];
  need: Need;
  clientId: string;
  selected: Recommendation | null;
  details: boolean;
  onSelect: (item: Recommendation, details: boolean) => void;
  onApply: (item: Recommendation) => void;
}) {
  const shown = details && selected ? [selected] : recommendations.slice(0, 2);
  return (
    <main className="screen centered-screen">
      <section className="recommendation-layout">
        <div className="recommendation-list">
          {shown.map((item) => (
            <ProductCard
              key={item.product_id}
              item={item}
              purpose={need.purpose}
              expanded={details}
              onDetails={() => onSelect(item, !details)}
              onApply={() => onApply(item)}
            />
          ))}
        </div>
        <ChatPanel
          key={selected?.product_id || "no-product"}
          clientId={clientId}
          need={need}
          product={selected}
          expanded={details}
        />
      </section>
    </main>
  );
}

function ApplicationScreen({ client, item, need, onClose, onSubmit, busy }: {
  client: Client;
  item: Recommendation;
  need: Need;
  onClose: () => void;
  onSubmit: (values: { revenue: number; expenses: number; debt: number; role: string }) => void;
  busy: boolean;
}) {
  const meta = clientMeta(client);
  const [revenue, setRevenue] = useState(1_200_000);
  const [expenses, setExpenses] = useState(950_000);
  const [debt, setDebt] = useState(0);
  const [role, setRole] = useState(client.legal_form === "ooo" ? "director" : "owner");
  return (
    <main className="screen centered-screen">
      <form className="application-card" onSubmit={(event) => { event.preventDefault(); onSubmit({ revenue, expenses, debt, role }); }}>
        <CloseButton onClick={onClose} />
        <h1>Заявка на кредит</h1>
        <div className="application-columns">
          <div className="application-fields">
            <Field label="Контактный телефон руководителя" value={meta.phone} />
            <Field label="Название компании" value={client.name} />
            <Field label="ИНН" value={client.inn} />
            <Field label="ОГРН" value={meta.ogrn} />
            <Field label="Дата регистрации" value={meta.registered} />
            <Field label="Вид деятельности" value={meta.activity} />
            <EditableField label="Выручка в месяц" value={revenue} type="number" min={0} onChange={(value) => setRevenue(Number(value))} />
            <EditableField label="Расходы в месяц" value={expenses} type="number" min={0} onChange={(value) => setExpenses(Number(value))} />
          </div>
          <div className="application-fields application-fields--offer">
            <Field label="Название кредита" value={item.name} wide />
            <div className="offer-grid">
              <Field label="Желаемая сумма кредита" value={money(need.amount)} />
              <Field label="Срок кредита" value={term(need.term_months)} />
              <Field label="Платеж" value={money(item.monthly_payment)} />
              <Field label="Ставка" value={percent(item.rate)} />
            </div>
            <Field label="Цель финансирования" value={purposeLabel(need.purpose)} wide />
            <EditableField label="Текущие платежи по кредитам" value={debt} type="number" min={0} onChange={(value) => setDebt(Number(value))} />
            {client.legal_form === "ooo" && (
              <label className="display-field display-field--editable">
                <span>Роль заявителя</span>
                <select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="director">Директор</option>
                  <option value="owner">Собственник</option>
                  <option value="accountant">Бухгалтер</option>
                  <option value="representative">Представитель</option>
                </select>
              </label>
            )}
            <div className="application-tags"><span>{need.collateral ? "С залогом" : "Без залога"}</span><span>{term(need.term_months)}</span></div>
          </div>
        </div>
        <PrimaryButton type="submit" disabled={busy} className="application-submit">{busy ? "Отправляем…" : "Отправить заявку"}</PrimaryButton>
      </form>
    </main>
  );
}

const STATUS_COPY: Record<string, { title: string; subtitle: string; stage: number; tone?: "danger" }> = {
  submitted: { title: "Заявка отправлена", subtitle: "Данные проверяются", stage: 1 },
  checking: { title: "Данные проверяются", subtitle: "Получаем сведения из внешних источников", stage: 1 },
  needs_info: { title: "Дополните данные", subtitle: "Данные проверяются", stage: 1 },
  scoring: { title: "Данные проверены", subtitle: "Проводится оценка заявки", stage: 2 },
  approved: { title: "Кредит одобрен", subtitle: "Банк подтвердил Вашу заявку", stage: 3 },
  counteroffer: { title: "Изменённые условия", subtitle: "Банк предлагает Вам другой вариант", stage: 2 },
  declined: { title: "Заявка не одобрена", subtitle: "Банк не подтвердил Вашу заявку", stage: 3, tone: "danger" },
  issued: { title: "Кредит оформлен", subtitle: "Новые данные теперь в Вашем личном кабинете", stage: 4 },
};

function Progress({ stage, danger = false }: { stage: number; danger?: boolean }) {
  const icons = ["status-check.svg", "status-document.svg", "status-chart.svg", "status-card.svg"];
  return (
    <div className="progress-row">
      {icons.map((icon, index) => {
        const number = index + 1;
        const active = number <= stage;
        const isDanger = danger && number === stage;
        return (
          <div className="progress-piece" key={icon}>
            {index > 0 && <span className={`progress-line ${number <= stage ? "active" : ""}${isDanger ? " danger" : ""}`} />}
            <span className={`progress-step${active ? " active" : ""}${isDanger ? " danger" : ""}`}>
              <img className="progress-circle" src={`${ASSETS}/${isDanger ? "status-danger.svg" : active ? "status-active.svg" : "status-idle.svg"}`} alt="" />
              <img className="progress-icon" src={`${ASSETS}/${icon}`} alt="" />
            </span>
          </div>
        );
      })}
    </div>
  );
}

function StatusExplanation({ clientId, application, onClose }: {
  clientId: string;
  application: CreditApplication;
  onClose: () => void;
}) {
  const decision = application.decision;
  const credit = application.credit_snapshot || {};
  const context = [
    `Текущая заявка №${application.id}. Статус: ${application.status}.`,
    `Продукт: ${String(credit.product_name || application.product_id || "не указан")}.`,
    `Сумма: ${money(application.amount)}. Срок: ${term(application.term_months)}. Цель: ${purposeLabel(application.purpose)}.`,
    `Выручка в месяц: ${money(application.declared_revenue)}. Расходы в месяц: ${money(application.declared_expenses)}. Текущие платежи: ${money(application.declared_debt_payment)}.`,
    `Класс риска: ${decision?.risk_class || "ещё не рассчитан"}. Вероятность дефолта: ${decision?.pd == null ? "ещё не рассчитана" : percent(decision.pd * 100)}.`,
    `Фактические причины решения: ${decision?.reasons.join("; ") || application.issues.join("; ") || "решение ещё формируется"}.`,
    `Факторы модели: ${decision?.factors.map((factor) => factor.text).filter(Boolean).join("; ") || "нет"}.`,
    `Прикреплённые документы: ${application.documents.map((document) => document.filename).join(", ") || "нет"}.`,
    `Используй get_my_applications с application_id=${application.id}, а для рассчитанного риска — assess_application_risk с application_id=${application.id}.`,
  ].join("\n");

  return <GlobalAssistant
    clientId={clientId}
    context={context}
    conversationKey={`status-${application.id}`}
    initialTitle={`Статус заявки №${application.id}`}
    initialPrompt="Объясни статус заявки простым языком. Используй только фактический статус, решение и факторы из контекста и tools."
    onClose={onClose}
  />;
}

function GlobalAssistant({ clientId, context, conversationKey, initialTitle, initialPrompt, onClose }: {
  clientId: string;
  context: string;
  conversationKey?: string;
  initialTitle?: string;
  initialPrompt?: string;
  onClose: () => void;
}) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const storageKey = `alfa-assistant-conversations:${clientId}`;
  const [conversations, setConversations] = useState<AssistantConversation[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "[]") as AssistantConversation[];
      if (conversationKey && !saved.some((conversation) => conversation.context_key === conversationKey)) {
        saved.unshift({ id: crypto.randomUUID(), title: initialTitle || "Новый чат", messages: [], created_at: new Date().toISOString(), context_key: conversationKey });
      }
      if (saved.length) return saved;
    } catch {
      // Повреждённая локальная история не должна ломать кабинет.
    }
    return [{ id: crypto.randomUUID(), title: "Новый чат", messages: [], created_at: new Date().toISOString() }];
  });
  const [activeId, setActiveId] = useState(() => conversations.find((conversation) => conversation.context_key === conversationKey)?.id || conversations[0].id);
  const active = conversations.find((conversation) => conversation.id === activeId) || conversations[0];

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(conversations));
  }, [conversations, storageKey]);

  function updateConversation(id: string, update: (conversation: AssistantConversation) => AssistantConversation) {
    setConversations((current) => current.map((conversation) => conversation.id === id ? update(conversation) : conversation));
  }

  function createConversation() {
    const conversation = { id: crypto.randomUUID(), title: "Новый чат", messages: [], created_at: new Date().toISOString() };
    setConversations((current) => [conversation, ...current]);
    setActiveId(conversation.id);
    setInput("");
  }

  async function sendText(text: string, visibleText = text) {
    const value = text.trim();
    if (!value || busy || !active) return;
    const conversationId = active.id;
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      title: conversation.messages.length === 0 && !conversation.context_key ? visibleText.slice(0, 42) : conversation.title,
      messages: [...conversation.messages, { role: "user", content: visibleText }],
    }));
    setInput("");
    setBusy(true);
    const message = `${context}\n\nЗапрос пользователя: ${value}`;
    try {
      const answer = await api.chat(clientId, `cabinet-${conversationId}`, message);
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [...conversation.messages, { role: "assistant", content: answer.response }],
      }));
    } catch (reason) {
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [...conversation.messages, { role: "assistant", content: reason instanceof Error ? reason.message : "Ассистент временно недоступен" }],
      }));
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    await sendText(input);
  }

  const autoStarted = useRef(false);
  useEffect(() => {
    if (!initialPrompt || autoStarted.current || !active) return;
    autoStarted.current = true;
    void sendText(initialPrompt, "Объясни статус заявки");
  }, [active?.id, initialPrompt]);

  return (
    <div className="assistant-backdrop" role="dialog" aria-modal="true" aria-label="ИИ-чат">
      <section className="assistant-modal assistant-modal--with-history">
        <aside className="assistant-history">
          <button type="button" className="assistant-new-chat" onClick={createConversation}>+ Новый чат</button>
          <div className="assistant-history__list">
            {conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.id}
                className={conversation.id === active?.id ? "active" : ""}
                onClick={() => setActiveId(conversation.id)}
              >
                <strong>{conversation.title}</strong>
                <span>{new Date(conversation.created_at).toLocaleDateString("ru-RU")}</span>
              </button>
            ))}
          </div>
        </aside>
        <header className="assistant-modal__header"><span>ИИ-помощник</span><CloseButton onClick={onClose} /></header>
        <div className="assistant-modal__body">
          {active?.messages.length === 0 && <p className="assistant-empty">Спросите о кредите, заявке или финансовых показателях — текущий контекст кабинета уже будет учтён.</p>}
          {active?.messages.map((message, index) => <div key={index} className={`chat-bubble chat-bubble--${message.role}`}><MarkdownMessage content={message.content} /></div>)}
          {busy && <div className="chat-bubble chat-bubble--assistant">Формирую ответ…</div>}
        </div>
        <form className="assistant-modal__input" onSubmit={(event) => { event.preventDefault(); void send(); }}>
          <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Введите запрос" />
          <button type="submit" aria-label="Отправить"><img src={`${ASSETS}/arrow.svg`} alt="" /></button>
        </form>
      </section>
    </div>
  );
}

function DocumentUploader({ application, clientId, onChange }: {
  application: CreditApplication;
  clientId: string;
  onChange: (application: CreditApplication) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const definitions = [
    ["bank_statement", "Выписка по счёту"],
    ["financial_report", "Финансовая отчётность"],
    ["income_confirmation", "Подтверждение доходов"],
  ];
  const uploaded = new Set(application.documents.map((document) => document.kind));

  async function upload(kind: string, file?: File) {
    if (!file) return;
    setBusy(kind);
    setError("");
    try {
      await api.uploadDocument(clientId, application.id, kind, file);
      onChange(await api.application(clientId, application.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось загрузить файл");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="document-uploader">
      {definitions.map(([kind, label]) => (
        <label key={kind} className={`document-button${uploaded.has(kind) ? " uploaded" : ""}`}>
          <img src={`${ASSETS}/document.svg`} alt="" />
          <span>{uploaded.has(kind) ? `${label} прикреплена` : busy === kind ? "Загрузка…" : `Прикрепить: ${label.toLowerCase()}`}</span>
          <input type="file" accept=".pdf,.txt,.csv,.md,.docx,.xlsx" onChange={(event) => void upload(kind, event.target.files?.[0])} />
        </label>
      ))}
      {error && <p className="form-error">{error}</p>}
    </div>
  );
}

function StatusScreen({ application, client, previewStatus, onClose, onChange, onEdit, onOther }: {
  application: CreditApplication;
  client: Client;
  previewStatus: string | null;
  onClose: () => void;
  onChange: (application: CreditApplication) => void;
  onEdit: () => void;
  onOther: () => void;
}) {
  const [explaining, setExplaining] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const status = previewStatus || application.status;
  const copy = STATUS_COPY[status] || STATUS_COPY.checking;
  const decision = application.decision;
  const meta = clientMeta(client);
  const company = application.client_snapshot || {};
  const credit = application.credit_snapshot || {};
  const allDocuments = ["bank_statement", "financial_report", "income_confirmation"].every((kind) => application.documents.some((document) => document.kind === kind));

  async function perform(action: () => Promise<CreditApplication>) {
    setBusy(true);
    setError("");
    try { onChange(await action()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Операция не выполнена"); } finally { setBusy(false); }
  }

  async function closeExplanation() {
    setExplaining(false);
    try {
      onChange(await api.application(client.id, application.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось обновить статус заявки");
    }
  }

  if (status === "issued") {
    return (
      <main className="screen centered-screen">
        <section className="issued-card">
          <CloseButton onClick={onClose} />
          <div className="issued-icon"><img src={`${ASSETS}/issued-circle.svg`} alt="" /><img src={`${ASSETS}/issued-check.svg`} alt="" /></div>
          <h1>Кредит оформлен</h1>
          <p>Новые данные теперь в Вашем<br />личном кабинете</p>
        </section>
      </main>
    );
  }

  return (
    <main className="screen centered-screen">
      <section className="status-card">
        <CloseButton onClick={onClose} />
        <Progress stage={copy.stage} danger={copy.tone === "danger"} />
        <div className="status-heading">
          <h1>{copy.title}</h1>
          <p><span className="status-dot" />{copy.subtitle}</p>
        </div>
        <div className="status-meta">
          <button className="text-link" onClick={() => setExplaining(true)}>Объяснить статус</button>
          <span>{new Date(application.updated_at).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })}</span>
        </div>

        {status === "submitted" && (
          <div className="status-summary-grid">
            <div className="summary-box"><span>Данные компании</span><ul><li>{String(company.phone || meta.phone)}</li><li>{String(company.company_name || client.name)}</li><li>ИНН {String(company.inn || client.inn)}</li><li>ОГРН {String(company.ogrn || meta.ogrn)}</li><li>{String(company.activity || meta.activity)}</li></ul></div>
            <div className="summary-box"><span>Условия кредита</span><ul><li>{String(credit.product_name || application.product_id || "Кредит")}</li><li>{money(application.amount)}</li><li>{term(application.term_months)}</li><li>{percent(snapshotNumber(credit.rate))}</li><li>{money(snapshotNumber(credit.monthly_payment))}</li><li>{purposeLabel(application.purpose)}</li></ul></div>
          </div>
        )}

        {status === "needs_info" && (
          <div className="needs-info-content">
            <p>Заполните недостающую информацию о бизнесе, чтобы мы могли продолжить рассмотрение.</p>
            {application.issues.length > 0 && <ul>{application.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
            <DocumentUploader application={application} clientId={client.id} onChange={onChange} />
            <PrimaryButton disabled={!allDocuments || busy} onClick={() => void perform(() => api.submit(client.id, application.id))}>{busy ? "Отправляем…" : "Отправить данные"}</PrimaryButton>
          </div>
        )}

        {status === "counteroffer" && (
          <div className="decision-content">
            <p>По результатам оценки текущая финансовая нагрузка не позволяет предложить запрошенную сумму.</p>
            {decision?.options.slice(0, 2).map((option, index) => <div className="counteroffer" key={index}><strong>{money(Number(option.amount || 0))}</strong><span>{term(Number(option.term_months || 0))}</span></div>)}
            <PrimaryButton disabled={busy} onClick={() => void perform(() => api.accept(client.id, application.id, 0))}>Принять предложение</PrimaryButton>
            <button className="text-link decision-secondary" onClick={onEdit}>Изменить параметры</button>
          </div>
        )}

        {status === "approved" && (
          <div className="approved-content">
            <div><p>✓ Компания подтверждена</p><p>✓ Регистрационные данные получены</p><p>✓ Финансовые данные получены</p><p>✓ Кредитная информация получена</p></div>
            <div><strong>Условия кредита одобрены:</strong><p>✓ {String(credit.product_name || application.product_id || "Кредит")}</p><p>✓ {money(decision?.amount || application.amount)}</p><p>✓ {term(decision?.term_months || application.term_months)}</p><p>✓ {money(decision?.monthly_payment ?? snapshotNumber(credit.monthly_payment))}</p><p>✓ {percent(decision?.rate ?? snapshotNumber(credit.rate))}</p></div>
            <PrimaryButton disabled={busy} onClick={() => void perform(() => api.finalize(client.id, application.id))}>Оформить кредит</PrimaryButton>
          </div>
        )}

        {status === "declined" && (
          <div className="decision-content">
            <p>{decision?.reasons.join(". ") || "Решение связано с текущими параметрами заявки и результатами оценки финансового риска."}</p>
            <PrimaryButton onClick={onEdit}>Изменить параметры</PrimaryButton>
            <button className="text-link decision-secondary" onClick={onOther}>Посмотреть другие варианты финансирования</button>
          </div>
        )}

        {(status === "checking" || status === "scoring") && <div className="status-checks"><p>✓ Компания подтверждена</p><p>✓ Регистрационные данные получены</p><p>✓ Финансовые данные получены</p><p>✓ Кредитная информация получена</p></div>}
        {error && <p className="form-error status-error">{error}</p>}
      </section>
      {explaining && <StatusExplanation clientId={client.id} application={application} onClose={() => void closeExplanation()} />}
    </main>
  );
}

export default function App() {
  const [view, setView] = useState<View>("login");
  const [profiles, setProfiles] = useState<Client[]>([]);
  const [demoClientId, setDemoClientId] = useState("");
  const [loading, setLoading] = useState(true);
  const [productNames, setProductNames] = useState<Record<string, string>>({});
  const [client, setClient] = useState<Client | null>(null);
  const [applications, setApplications] = useState<CreditApplication[]>([]);
  const [application, setApplication] = useState<CreditApplication | null>(null);
  const [previewStatus, setPreviewStatus] = useState<string | null>(null);
  const [need, setNeed] = useState<Need>({ purpose: "investment", amount: 1_200_000, term_months: 36, collateral: false });
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [details, setDetails] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const activeClientId = useRef<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [briefs, catalog] = await Promise.all([api.clients(), api.products()]);
        setProductNames(Object.fromEntries(catalog.map((product) => [product.id, product.name])));
        const loaded = await Promise.all(briefs.map((brief) => api.profile(brief.id)));
        setProfiles(loaded);
        const remembered = localStorage.getItem("alfa-client-id");
        const demoProfiles = loaded.filter((item) => item.id.startsWith("demo_"));
        const suggested = demoProfiles.find((item) => item.id === remembered)
          || demoProfiles.find((item) => item.id === "demo_cafe")
          || demoProfiles[0];
        setDemoClientId(suggested?.id || "");
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Backend недоступен");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!client) return;
    activeClientId.current = client.id;
    setApplications([]);
    setApplication(null);
    localStorage.setItem("alfa-client-id", client.id);
    void refreshApplications(client.id);
  }, [client]);

  async function refreshApplications(clientId = client?.id) {
    if (!clientId) return;
    try {
      const loaded = await api.applications(clientId);
      if (activeClientId.current === clientId) {
        setApplications(loaded.filter((item) => item.client_id === clientId));
      }
    } catch (reason) {
      if (activeClientId.current === clientId) setError(reason instanceof Error ? reason.message : "Не удалось получить заявки");
    }
  }

  function selectClient(next: Client) {
    activeClientId.current = next.id;
    setApplications([]);
    setApplication(null);
    setRecommendations([]);
    setSelected(null);
    setDetails(false);
    setAssistantOpen(false);
    setClient(next);
  }

  function completeRegistration(registered: Client, meta: typeof fallbackMeta) {
    localStorage.setItem(`alfa-client-meta:${registered.id}`, JSON.stringify(meta));
    setProfiles((current) => [...current.filter((item) => item.id !== registered.id), registered]);
    selectClient(registered);
    setView("home");
  }

  async function findProducts(nextNeed: Need) {
    if (!client) { setView("login"); return; }
    setBusy(true);
    setError("");
    try {
      const result = await api.recommend(client.id, nextNeed);
      setNeed(nextNeed);
      setRecommendations(result);
      setSelected(result[0] || null);
      setDetails(false);
      setView("recommendations");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось подобрать продукты");
    } finally { setBusy(false); }
  }

  async function submitApplication(values: { revenue: number; expenses: number; debt: number; role: string }) {
    if (!client || !selected) return;
    const meta = clientMeta(client);
    setBusy(true);
    setError("");
    try {
      const draft = await api.createApplication(client.id, {
        product_id: selected.product_id,
        amount: need.amount,
        term_months: need.term_months,
        purpose: need.purpose,
        declared_revenue: values.revenue,
        declared_expenses: values.expenses,
        declared_debt_payment: values.debt,
        applicant_role: values.role,
        collateral_asset_id: need.collateral ? client.assets[0]?.id : null,
        bki_consent: true,
        client_snapshot: {
          owner_name: client.owner_name,
          company_name: client.name,
          inn: client.inn,
          ogrn: meta.ogrn,
          registration_date: meta.registered,
          activity: meta.activity,
          phone: meta.phone,
        },
        credit_snapshot: {
          product_id: selected.product_id,
          product_name: selected.name,
          rate: selected.rate,
          monthly_payment: selected.monthly_payment,
          overpayment: selected.overpayment,
          risk_class: selected.risk_class,
          pd: selected.pd,
          collateral: need.collateral,
        },
      });
      const resolved = await api.submit(client.id, draft.id);
      setApplication(resolved);
      setPreviewStatus("submitted");
      setView("status");
      await refreshApplications(client.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось отправить заявку");
    } finally { setBusy(false); }
  }

  async function track(next: CreditApplication) {
    if (!client) return;
    try {
      const full = await api.application(client.id, next.id);
      setApplication(full);
      setNeed({
        purpose: full.purpose || "investment",
        amount: full.amount || 1_200_000,
        term_months: full.term_months || 36,
        collateral: Boolean(full.credit_snapshot?.collateral || full.collateral_asset_id),
      });
      setPreviewStatus(null);
      setView("status");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось открыть заявку"); }
  }

  const currentClient = client;
  const demoProfiles = useMemo(() => profiles.filter((item) => item.id.startsWith("demo_")), [profiles]);
  const selectedDemoClient = useMemo(
    () => demoProfiles.find((item) => item.id === demoClientId) || null,
    [demoProfiles, demoClientId],
  );
  const assistantContext = useMemo(() => [
    "Контекст текущего кредитного кабинета. Не спрашивай повторно перечисленные данные.",
    `Клиент: ${currentClient?.name || "не выбран"}; client_id: ${currentClient?.id || "нет"}.`,
    `Потребность: ${purposeLabel(need.purpose)}, сумма ${money(need.amount)}, срок ${term(need.term_months)}, ${need.collateral ? "с залогом" : "без залога"}.`,
    selected ? `Выбранный продукт: ${selected.name}; ставка ${percent(selected.rate)}; платёж ${money(selected.monthly_payment)}; переплата ${money(selected.overpayment)}; риск ${selected.risk_class}, PD ${percent(selected.pd * 100)}.` : "Продукт ещё не выбран.",
    application ? `Текущая заявка №${application.id}, статус ${application.status}, продукт ${String(application.credit_snapshot?.product_name || application.product_id || "не указан")}, сумма ${money(application.amount)}, срок ${term(application.term_months)}, ставка ${percent(snapshotNumber(application.credit_snapshot?.rate))}, платёж ${money(snapshotNumber(application.credit_snapshot?.monthly_payment))}, выручка ${money(application.declared_revenue)}, расходы ${money(application.declared_expenses)}, текущие платежи ${money(application.declared_debt_payment)}.` : "Открытой заявки в контексте нет.",
    "Если вопрос относится к риску компании в целом и пользователь не назвал заявку, используй assess_company_risk и не требуй ID заявки.",
  ].join("\n"), [currentClient, need, selected, application]);

  const hasNavigation = Boolean(currentClient && view !== "login" && view !== "register");
  const visibleApplications = currentClient
    ? applications.filter((item) => item.client_id === currentClient.id)
    : [];

  return (
    <div className={`app-shell${hasNavigation ? " app-shell--with-nav" : ""}`}>
      {error && <div className="global-error"><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
      {hasNavigation && (
        <Navigation
          view={view}
          assistantOpen={assistantOpen}
          onNavigate={(next) => { if (next === "applications") void refreshApplications(); setView(next); }}
          onAssistant={() => setAssistantOpen(true)}
        />
      )}
      {view === "home" && <HomeScreen client={currentClient} onFinance={() => setView(currentClient ? "wizard" : "login")} />}
      {view === "login" && !loading && <LoginScreen clients={profiles} selectedClient={selectedDemoClient} onLogin={(next) => { selectClient(next); setView("home"); }} onRegister={() => setView("register")} />}
      {view === "register" && <RegisterScreen onDone={completeRegistration} onClose={() => setView("login")} />}
      {view === "dashboard" && currentClient && <DashboardScreen client={currentClient} applications={visibleApplications} onNew={() => setView("wizard")} onApplications={() => setView("applications")} />}
      {view === "applications" && <ApplicationsScreen applications={visibleApplications} productNames={productNames} onOpen={(next) => void track(next)} onClose={() => setView("dashboard")} />}
      {view === "wizard" && <CreditWizard initial={need} onSubmit={(value) => void findProducts(value)} busy={busy} />}
      {(view === "recommendations" || view === "details") && currentClient && <RecommendationsScreen recommendations={recommendations} need={need} clientId={currentClient.id} selected={selected} details={details} onSelect={(item, expanded) => { setSelected(item); setDetails(expanded); setView(expanded ? "details" : "recommendations"); }} onApply={(item) => { setSelected(item); setView("application"); }} />}
      {view === "application" && currentClient && selected && <ApplicationScreen client={currentClient} item={selected} need={need} onClose={() => setView("recommendations")} onSubmit={(values) => void submitApplication(values)} busy={busy} />}
      {view === "status" && currentClient && application && <StatusScreen application={application} client={currentClient} previewStatus={previewStatus} onClose={() => { setPreviewStatus(null); setView("dashboard"); void refreshApplications(); }} onChange={(next) => { setApplication(next); setPreviewStatus(null); void refreshApplications(); }} onEdit={() => setView("wizard")} onOther={() => setView("recommendations")} />}
      {loading && !error && <div className="loading-screen">Загружаем кредитный кабинет…</div>}
      {assistantOpen && currentClient && <GlobalAssistant key={currentClient.id} clientId={currentClient.id} context={assistantContext} onClose={() => setAssistantOpen(false)} />}
      {demoProfiles.length > 0 && view === "login" && !loading && (
        <label className="demo-switcher">
          <span>Пример пользователя</span>
          <select value={demoClientId} onChange={(event) => setDemoClientId(event.target.value)}>
            {demoProfiles.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
      )}
    </div>
  );
}
