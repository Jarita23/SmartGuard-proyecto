-- SmartGuard: esquema normalizado (3 tablas) para documentación y despliegue en Supabase.
-- Ejecutar en SQL Editor o como migración según tu flujo.

create extension if not exists "pgcrypto";

-- Usuarios del sistema (operadores, administradores)
create table if not exists public.usuarios (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    nombre text not null,
    rol text not null default 'operador',
    created_at timestamptz not null default now()
);

-- Cámaras asociadas a un usuario responsable (id bigint acorde a despliegue actual)
create table if not exists public.camaras (
    id bigint generated always as identity primary key,
    usuario_id uuid references public.usuarios (id) on delete set null,
    nombre text not null,
    ubicacion text,
    activa boolean not null default true,
    indice_dispositivo int not null default 0,
    created_at timestamptz not null default now()
);

-- Alertas generadas por el pipeline de detección
create table if not exists public.alertas (
    id uuid primary key default gen_random_uuid(),
    camara_id bigint not null references public.camaras (id) on delete cascade,
    tipo text not null,
    severidad text not null,
    descripcion text,
    metadata jsonb not null default '{}'::jsonb,
    procesada boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists idx_alertas_camara on public.alertas (camara_id);
create index if not exists idx_alertas_created on public.alertas (created_at desc);

-- Habilitar RLS y políticas según tu modelo de auth (Supabase Auth recomendado).
-- alter table public.usuarios enable row level security;
-- alter table public.camaras enable row level security;
-- alter table public.alertas enable row level security;
