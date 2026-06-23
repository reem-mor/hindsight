-- HINDSIGHT semantic search — Supabase pgvector (run in Supabase SQL editor)
-- Alternative: Pinecone index with same metadata fields.

create extension if not exists vector;

create table if not exists hindsight_incidents (
  document_id text primary key,
  filename text,
  classification text,
  department text,
  sensitivity text,
  routing_tag text,
  summary text,
  embedding vector(768),
  processed_at timestamptz,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists hindsight_incidents_embedding_idx
  on hindsight_incidents using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- RPC for similarity search (cosine distance; lower = more similar)
create or replace function match_hindsight_incidents(
  query_embedding vector(768),
  match_count int default 5,
  match_threshold float default 0.25
)
returns table (
  document_id text,
  filename text,
  classification text,
  summary text,
  routing_tag text,
  sensitivity text,
  similarity float
)
language sql stable
as $$
  select
    document_id,
    filename,
    classification,
    summary,
    routing_tag,
    sensitivity,
    1 - (embedding <=> query_embedding) as similarity
  from hindsight_incidents
  where embedding is not null
    and (1 - (embedding <=> query_embedding)) >= match_threshold
  order by embedding <=> query_embedding
  limit match_count;
$$;
