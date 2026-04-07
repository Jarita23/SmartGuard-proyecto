import { createClient } from '@supabase/supabase-js'

// --- BYPASS DE EMERGENCIA PARA TESIS ---
// Saltamos el archivo .env porque el sistema local no lo está leyendo
const supabaseUrl = "https://hormehwklsianndhuojf.supabase.co"
const supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhvcm1laHdrbHNpYW5uZGh1b2pmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ5Mjc4MjMsImV4cCI6MjA5MDUwMzgyM30.SewDjczb7a3D-aYgqc7UudZWd9WxeWFMlEKEDxCAric"

console.log("🚀 SmartGuard: Conexión forzada activa. Ignorando archivo .env");

export const supabase = createClient(supabaseUrl, supabaseAnonKey)