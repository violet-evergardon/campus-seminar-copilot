export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

export interface EventItem {
  id:number; title:string; speaker?:string; speaker_affiliation?:string; start_time?:string; end_time?:string;
  location?:string; location_mode:'online'|'offline'|'hybrid'; organizer?:string; field_tags:string[];
  abstract?:string; source_url?:string; source_type:string; source_site?:string;
  status:'draft'|'published'|'rejected'|'expired'; extraction_confidence:number; quality_score:number;
  created_at:string; updated_at:string;
}
export interface RankedEvent extends EventItem {
  final_score:number; semantic_score:number; keyword_score:number; time_score:number; interest_score:number; reason:string;
}
export interface SearchResponse {items:RankedEvent[]; total:number; page:number; page_size:number}

async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response = await fetch(`${API_BASE}${path}`, {headers:{'Content-Type':'application/json', ...(init?.headers||{})}, ...init})
  if(!response.ok){const body=await response.json().catch(()=>({detail:response.statusText})); throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail))}
  if(response.status===204) return undefined as T
  return response.json()
}
export const api = {
  health:()=>request<Record<string,unknown>>('/api/health'),
  search:(body:Record<string,unknown>)=>request<SearchResponse>('/api/search',{method:'POST',body:JSON.stringify(body)}),
  recommend:()=>request<RankedEvent[]>('/api/recommend?user_id=1&limit=8'),
  chat:(question:string)=>request<{answer:string;events:RankedEvent[];interpreted_time?:string;rounds:number}>('/api/chat',{method:'POST',body:JSON.stringify({question})}),
  favorite:(eventId:number)=>request(`/api/favorites?event_id=${eventId}`,{method:'POST',body:JSON.stringify({user_id:1})}),
  parseText:(text:string)=>request<EventItem>('/api/admin/parse-text',{method:'POST',body:JSON.stringify({text,source_site:'人工粘贴'})}),
  adminEvents:()=>request<EventItem[]>('/api/admin/events'),
  updateEvent:(id:number,body:Partial<EventItem>)=>request<EventItem>(`/api/admin/events/${id}`,{method:'PATCH',body:JSON.stringify(body)}),
  review:(id:number,action:'publish'|'reject')=>request<EventItem>(`/api/admin/events/${id}/${action}`,{method:'POST',body:JSON.stringify({reviewer:'local-admin'})}),
  sources:()=>request<any[]>('/api/admin/crawl/sources'), runs:()=>request<any[]>('/api/admin/crawl/runs'),
  crawl:(mode:'fixture'|'live')=>request<any>('/api/admin/crawl/run',{method:'POST',body:JSON.stringify({mode})}),
  badCases:()=>request<any[]>('/api/admin/bad-cases'), resolveCase:(id:number)=>request(`/api/admin/bad-cases/${id}?new_status=resolved`,{method:'PATCH'}),
  feedback:(eventId:number)=>request('/api/feedback',{method:'POST',body:JSON.stringify({user_id:1,event_id:eventId,feedback_type:'helpful',content:'推荐有帮助'})}),
  async upload(file:File){const form=new FormData();form.append('file',file);const response=await fetch(`${API_BASE}/api/admin/upload`,{method:'POST',body:form});if(!response.ok){const body=await response.json();throw new Error(body.detail||'上传失败')}return response.json() as Promise<EventItem>}
}
