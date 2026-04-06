export interface User {
  id: string
  username: string
  role: string
  is_active: boolean
  canary_enabled: boolean
  created_at: string
  updated_at: string
  version: number
}

export interface Resident {
  id: string
  user_id: string
  unit_id: string
  first_name: string
  last_name: string
  email: string | null
  phone: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface Property {
  id: string
  name: string
  address: string | null
  billing_day: number
  late_fee_days: number
  late_fee_amount: string
  tax_rate: string
  created_at: string
  updated_at: string
  version: number
}

export interface Unit {
  id: string
  property_id: string
  unit_number: string
  status: string
  created_at: string
  updated_at: string
  version: number
}

export interface Bill {
  id: string
  resident_id: string
  property_id: string
  billing_period: string
  due_date: string
  subtotal: string
  tax_total: string
  late_fee: string
  total: string
  balance_due: string
  status: string
  line_items: BillLineItem[]
  generated_at: string
  created_at: string
  updated_at: string
  version: number
}

export interface BillLineItem {
  id: string
  description: string
  amount: string
  tax_amount: string
}

export interface Payment {
  id: string
  bill_id: string
  resident_id: string
  amount: string
  payment_method: string
  evidence_media_id: string | null
  status: string
  reviewed_by: string | null
  reviewed_at: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface Order {
  id: string
  resident_id: string
  property_id: string
  title: string
  description: string | null
  category: string | null
  priority: string
  status: string
  assigned_to: string | null
  milestones: OrderMilestone[]
  created_at: string
  updated_at: string
  version: number
}

export interface OrderMilestone {
  from_status: string | null
  to_status: string
  changed_by: string
  notes: string | null
  created_at: string
}

export interface Listing {
  id: string
  property_id: string
  created_by: string
  title: string
  description: string | null
  category: string
  price: string | null
  status: string
  published_at: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface Media {
  id: string
  filename: string
  original_name: string
  mime_type: string
  file_size: number
  created_at: string
}

export interface CreditMemo {
  id: string
  resident_id: string
  bill_id: string | null
  order_id: string | null
  amount: string
  reason: string
  status: string
  applied_to_bill_id: string | null
  created_by: string
  approved_by: string | null
  created_at: string
  updated_at: string
  version: number
}

export interface ContentConfig {
  id: string
  name: string
  status: string
  created_by: string
  published_at: string | null
  sections: ContentSection[]
  created_at: string
  updated_at: string
  version: number
}

export interface ContentSection {
  id: string
  config_id: string
  section_type: string
  title: string | null
  content_json: Record<string, unknown>
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
  version: number
}

export interface ConflictResponse {
  error: 'conflict'
  message: string
  your_version: number
  server_version: number
  your_data: Record<string, unknown>
  server_data: Record<string, unknown>
  changed_fields: string[]
}

export interface QueuedWrite {
  id: string
  method: string
  url: string
  data: Record<string, unknown> | null
  headers: Record<string, string>
  idempotencyKey: string
  createdAt: number
  retryCount: number
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: {
    id: string
    username: string
    role: string
    canary_enabled: boolean
  }
}

export interface ApiError {
  detail: string | ConflictResponse
}
