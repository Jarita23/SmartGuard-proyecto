import React, { useEffect, useState } from 'react';
import { supabase } from './supabase';
import { Shield, Bell, Camera, AlertTriangle, CheckCircle, Activity } from 'lucide-react';

function App() {
  const [alertas, setAlertas] = useState([]);
  const [loading, setLoading] = useState(true);

  // 1. Cargar alertas iniciales y suscribirse al tiempo real
  useEffect(() => {
    const fetchAlertas = async () => {
      const { data } = await supabase
        .from('alertas')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(10);
      setAlertas(data || []);
      setLoading(false);
    };

    fetchAlertas();

    // SUSCRIPCIÓN REALTIME: La magia de tu tesis
    const channel = supabase
      .channel('schema-db-changes')
      .on('postgres_changes', 
        { event: 'INSERT', schema: 'public', table: 'alertas' }, 
        (payload) => {
          setAlertas((current) => [payload.new, ...current]);
          // Opcional: Sonido de alerta
          const audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
          audio.play();
        }
      )
      .subscribe();

    return () => supabase.removeChannel(channel);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 p-4 sticky top-0 backdrop-blur-md z-10">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="bg-red-600 p-2 rounded-lg animate-pulse">
              <Shield size={24} className="text-white" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">
              SmartGuard <span className="text-red-500 text-sm font-mono">LIVE v2.5</span>
            </h1>
          </div>
          <div className="flex items-center gap-4 text-sm font-medium">
            <div className="flex items-center gap-2 text-green-400 bg-green-400/10 px-3 py-1 rounded-full">
              <Activity size={16} /> API Online
            </div>
            <div className="text-slate-400 italic">Talca, Maule</div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Columna Izquierda: Vista de Cámara (Simulada) */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/80">
              <div className="flex items-center gap-2">
                <Camera size={18} className="text-slate-400" />
                <span className="font-semibold uppercase tracking-wider text-xs">Cámara Principal - Pasillo 01</span>
              </div>
              <span className="bg-red-500/20 text-red-500 text-[10px] font-bold px-2 py-0.5 rounded animate-pulse">REC</span>
            </div>
            <div className="aspect-video bg-black flex items-center justify-center relative group">
              <div className="absolute inset-0 opacity-20 pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')]"></div>
              <p className="text-slate-600 font-mono text-sm">TRANSMISIÓN ENCRIPTADA...</p>
              {/* Overlay de IA */}
              <div className="absolute top-4 left-4 border-2 border-red-500 w-32 h-32 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="bg-red-500 text-[10px] text-white absolute -top-5 px-1">Sujeto Sospechoso</span>
              </div>
            </div>
          </div>
        </div>

        {/* Columna Derecha: Feed de Alertas */}
        <div className="space-y-4">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Bell size={20} className="text-red-500" /> Historial de Alertas
            </h2>
            <span className="text-xs text-slate-500">Últimas 10</span>
          </div>

          <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-200px)] pr-2 custom-scrollbar">
            {loading ? (
              <p className="text-center text-slate-500 py-10">Conectando con la IA...</p>
            ) : alertas.length === 0 ? (
              <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl text-center">
                <CheckCircle className="mx-auto mb-2 text-green-500" />
                <p className="text-sm text-slate-400">Todo despejado en Talca</p>
              </div>
            ) : (
              alertas.map((alerta) => (
                <div 
                  key={alerta.id} 
                  className={`p-4 rounded-xl border transition-all duration-500 animate-in slide-in-from-right-5 ${
                    alerta.severidad === 'alta' 
                    ? 'bg-red-500/10 border-red-500/50 shadow-lg shadow-red-500/5' 
                    : 'bg-slate-900 border-slate-800'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                      alerta.severidad === 'alta' ? 'bg-red-500 text-white' : 'bg-slate-700 text-slate-300'
                    }`}>
                      {alerta.severidad}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {new Date(alerta.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <h3 className="font-bold text-sm mb-1">{alerta.etiqueta}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed italic">
                    "{alerta.descripcion}"
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;