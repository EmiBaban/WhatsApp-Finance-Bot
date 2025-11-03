export interface Account {
  id: number;
  iban: string;
  banca: string;
  compania: string;
  sum: number;
  created_at: string;
}

export interface Transaction {
  id: number;
  amount: number;
  currency: string;
  invoice_number?: string;
  profile_name: string;
  account: string;
  description?: string;
  created_at: string;
}

export interface Stats {
  total_balance: number;
  transaction_count: number;
  recent_transactions: Transaction[];
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
  pagination?: Pagination;
}
