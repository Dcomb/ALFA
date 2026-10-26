export type View =
  | "home"
  | "login"
  | "register"
  | "dashboard"
  | "wizard"
  | "recommendations"
  | "details"
  | "application"
  | "applications"
  | "status";

export type NeedTag =
  | "cash_gap"
  | "working_capital"
  | "investment"
  | "refinancing"
  | "vehicle"
  | "real_estate"
  | "tender"
  | "small_expenses"
  | "any";

export interface ClientBrief {
  id: string;
  name: string;
  legal_form: "ip" | "ooo";
}

export interface Asset {
  id: number;
  kind: string;
  description: string;
  market_value: number;
}

export interface Client extends ClientBrief {
  inn: string;
  okved: string;
  tax_regime: string;
  has_alfa_account: boolean;
  owner_name: string;
  owner_age: number | null;
  ogrn: string | null;
  registration_date: string | null;
  phone: string | null;
  assets: Asset[];
}

export interface Recommendation {
  product_id: string;
  name: string;
  score: number;
  pd: number;
  risk_class: "A" | "B" | "C" | "D";
  rate: number | null;
  amount: number | null;
  max_amount: number | null;
  term_months: number | null;
  monthly_payment: number | null;
  overpayment: number | null;
  reasons: string[];
  warnings: string[];
}

export interface Decision {
  outcome: string;
  pd: number | null;
  risk_class: string | null;
  amount: number | null;
  term_months: number | null;
  rate: number | null;
  monthly_payment: number | null;
  reasons: string[];
  factors: Array<{ name?: string; text?: string; impact?: number; points?: number }>;
  options: Array<Record<string, unknown>>;
  model_version: string | null;
  created_at: string;
}

export interface ApplicationDocument {
  id: number;
  kind: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
}

export interface CreditApplication {
  id: number;
  client_id: string;
  status: string;
  product_id: string | null;
  amount: number | null;
  term_months: number | null;
  purpose: NeedTag | null;
  declared_revenue: number | null;
  declared_expenses: number | null;
  declared_debt_payment: number | null;
  applicant_role: string | null;
  collateral_asset_id: number | null;
  bki_consent: boolean;
  info_rounds: number;
  issues: string[];
  decision: Decision | null;
  accepted_option: Record<string, unknown> | null;
  client_snapshot: Record<string, unknown>;
  credit_snapshot: Record<string, unknown>;
  documents: ApplicationDocument[];
  created_at: string;
  updated_at: string;
}

export interface Need {
  purpose: NeedTag;
  amount: number;
  term_months: number;
  collateral: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantConversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  context_key?: string;
}
