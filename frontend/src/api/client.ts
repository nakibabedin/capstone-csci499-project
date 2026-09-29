// Thin wrapper around fetch for talking to the Flask backend.
// In dev, Vite proxies /api to http://localhost:5001 (see vite.config.ts).

export interface Item {
  id: number
  name: string
  description: string
}

export interface User {
  id: number
  name: string
  email: string
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error ?? `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  getItems: () => request<Item[]>('/items'),
  getItem: (id: number) => request<Item>(`/items/${id}`),
  createItem: (item: Omit<Item, 'id'>) =>
    request<Item>('/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(item),
    }),
  deleteItem: (id: number) =>
    request<{ deleted: number }>(`/items/${id}`, { method: 'DELETE' }),

  getUsers: () => request<User[]>('/users'),

  uploadFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{ filename: string; size: number; message: string }>(
      '/upload',
      { method: 'POST', body: form },
    )
  },
}
