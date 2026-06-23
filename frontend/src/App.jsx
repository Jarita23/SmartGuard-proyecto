import React, { useEffect, useState } from 'react';
import { supabase } from './supabase'; 
import Login from './components/Login'; 
import { Shield, Bell, Camera, CheckCircle, Activity, AlertTriangle, FileText, Smartphone, LogOut, X } from 'lucide-react';

// 🚀 Limpia comillas y barras residuales
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000')
  .replace(/^"|"/g, '')
  .replace(/\/$/, '');

console.log("📡 SmartGuard conectando al Backend en:", `${API_BASE_URL}/video_feed`);

function App() {
  const [session, setSession] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [alertas, setAlertas] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Controla si hay una imagen ampliada en pantalla
  const [imagenAmpliada, setImagenAmpliada] = useState(null);

  useEffect(() => {
    const wipeSession = async () => {
      await supabase.auth.signOut();
      setSession(null);
      setIsAuthLoading(false);
    };
    
    wipeSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) return; 

    const fetchAlertas = async () => {
      const { data } = await supabase
        .from('alertas')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(15);
      
      setAlertas(data || []);
      setLoading(false);
    };

    fetchAlertas();

    const channel = supabase
      .channel('schema-db-changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alertas' }, (payload) => {
        setAlertas((current) => [payload.new, ...current]);
        
        // 🚀 NUEVO SONIDO: "Pop" tecnológico corregido y permanente
        const audio = new Audio('https://assets.mixkit.co/sfx/preview/mixkit-message-pop-alert-2354.mp3');
        audio.volume = 1.0;
        
        audio.play().catch(() => {
          console.log('🔇 Audio bloqueado por el navegador. Haz un clic en el panel para activar el sonido.');
        });
      })
      .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'alertas' }, (payload) => {
        setAlertas((current) => current.map(a => a.id === payload.new.id ? payload.new : a));
      })
      .on('postgres_changes', { event: 'DELETE', schema: 'public', table: 'alertas' }, (payload) => {
        setAlertas((current) => current.filter(a => a.id !== payload.old.id));
      })
      .subscribe();

    return () => supabase.removeChannel(channel);
  }, [session]); 

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const alertasVisibles = alertas.filter(a => a.estado_validacion !== 'falsa_alarma');

  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-[#050914] flex justify-center items-center">
        <div className="flex flex-col items-center gap-4">
          <Shield className="w-12 h-12 text-red-600 animate-pulse" />
          <p className="text-red-600 tracking-widest text-sm font-mono">INICIANDO SISTEMA...</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-[#0a0f18] text-slate-200 font-sans selection:bg-red-500/30">
      
      {/* 🚀 MODAL DE IMAGEN PANTALLA COMPLETA */}
      {imagenAmpliada && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4 backdrop-blur-sm cursor-zoom-out" 
          onClick={() => setImagenAmpliada(null)}
        >
          <div className="relative max-w-6xl w-full h-full flex items-center justify-center" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setImagenAmpliada(null)} 
              className="absolute top-4 right-4 bg-red-600/80 p-2 rounded-full text-white hover:bg-red-500 transition-colors z-50"
            >
              <X size={24} />
            </button>
            <img 
              src={imagenAmpliada} 
              alt="Evidencia Ampliada" 
              className="max-w-full max-h-full object-contain rounded-md border border-slate-700 shadow-[0_0_40px_rgba(220,38,38,0.2)]" 
            />
          </div>
        </div>
      )}

      <header className="border-b border-slate-800 bg-[#0d131f] p-3 sticky top-0 z-10 flex justify-between items-center shadow-md">
        <div className="flex items-center gap-3 ml-4">
          <div className="bg-red-600 p-1.5 rounded animate-pulse">
            <Shield size={20} className="text-white" />
          </div>
          <h1 className="text-xl font-bold tracking-tight uppercase">
            SmartGuard <span className="text-red-500 text-xs font-mono ml-1">EN VIVO</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-4 text-xs font-medium mr-4">
          <div className="flex items-center gap-1.5 text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 px-2 py-1 rounded-sm">
            <Activity size={14} /> SEGURO
          </div>
          <div className="text-slate-500 uppercase tracking-widest font-mono">TALCA</div>
          
          <button 
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-slate-400 hover:text-red-500 hover:bg-red-500/10 px-2 py-1 rounded-sm transition-colors ml-2"
            title="Desconectar Operador"
          >
            <LogOut size={14} />
            <span className="hidden md:inline uppercase tracking-widest font-mono text-[10px]">Salir</span>
          </button>
        </div>
      </header>

      <main className="p-4 grid grid-cols-1 lg:grid-cols-4 gap-4">
        
        <div className="lg:col-span-3 flex flex-col gap-4">
          <div className="bg-[#0d131f] rounded-sm border border-slate-800 shadow-lg overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-800 flex justify-between items-center bg-black/40">
              <div className="flex items-center gap-2">
                <Camera size={16} className="text-slate-400" />
                <span className="font-bold uppercase tracking-widest text-xs text-slate-300">CAM-01 / Pasillo Principal</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-slate-500">FPS: 30</span>
                <span className="bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-sm animate-pulse tracking-widest">REC</span>
              </div>
            </div>
            
            <div className="aspect-video bg-black relative group flex items-center justify-center">
              {/* 🚀 Enlace limpio, sin brackets */}
              <div className="absolute inset-0 opacity-10 pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')]"></div>
              <img 
                src={`${API_BASE_URL}/video_feed`} 
                alt="Feed CAM-01" 
                className="w-full h-full object-contain relative z-10" 
              />
            </div>
          </div>
        </div>

        <div className="bg-[#0d131f] border border-slate-800 rounded-sm flex flex-col shadow-lg overflow-hidden lg:h-[calc(100vh-100px)]">
          <div className="p-3 border-b border-slate-800 bg-black/40 flex items-center justify-between">
            <h2 className="text-sm font-bold flex items-center gap-2 uppercase tracking-wide">
              <Bell size={16} className="text-red-500" /> Eventos
            </h2>
            <span className="text-[10px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded-sm">
              {alertasVisibles.length} ACTIVOS
            </span>
          </div>

          <div className="flex-grow overflow-y-auto p-3 space-y-3 custom-scrollbar">
            {loading ? (
              <p className="text-center text-slate-500 py-10 font-mono text-xs">Sincronizando nodo...</p>
            ) : alertasVisibles.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-slate-600">
                <Shield size={32} className="mb-2 opacity-50" />
                <p className="text-xs uppercase tracking-widest">Sin Detecciones</p>
              </div>
            ) : (
              alertasVisibles.map((alerta) => (
                <div 
                  key={alerta.id} 
                  className={`rounded-sm border transition-all duration-300 ${
                    alerta.estado_validacion === 'riesgo_alto' 
                    ? 'bg-red-950/20 border-red-900 shadow-md' 
                    : 'bg-slate-900 border-slate-700'
                  }`}
                >
                  <div className="p-3">
                    <div className="flex justify-between items-start mb-1.5">
                      <div className="flex items-center gap-2">
                        <AlertTriangle size={14} className={alerta.estado_validacion === 'riesgo_alto' ? 'text-red-500' : 'text-amber-500'} />
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-sm uppercase tracking-wider ${
                          alerta.estado_validacion === 'riesgo_alto' ? 'bg-red-600 text-white' : 'bg-amber-500/20 text-amber-400'
                        }`}>
                          {alerta.estado_validacion === 'riesgo_alto' ? 'ROBO CONFIRMADO' : 'ANOMALÍA DETECTADA'}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(alerta.created_at).toLocaleTimeString('es-CL', {hour12: false})}
                      </span>
                    </div>
                    
                    <h3 className="font-bold text-sm text-slate-200 mt-2">{alerta.etiqueta}</h3>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                      {alerta.descripcion}
                    </p>

                    {alerta.estado_validacion === 'pendiente' && (
                      <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-center gap-2 text-slate-500 bg-slate-950/50 p-2 rounded-sm">
                        <Smartphone size={14} className="animate-pulse text-amber-500" />
                        <span className="text-[9px] uppercase tracking-widest font-mono">Esperando decisión en Telegram...</span>
                      </div>
                    )}
                  </div>

                  {alerta.estado_validacion === 'riesgo_alto' && (
                    <div className="bg-black/50 border-t border-red-900/50 p-3">
                      <div className="aspect-video bg-slate-900 border border-slate-800 rounded-sm mb-3 relative overflow-hidden group">
                        {/* 🚀 Enlace de imagen limpio */}
                        <img 
                          src={alerta.imagen_url || "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&q=80&w=400"} 
                          alt="Evidencia Forense" 
                          onClick={() => setImagenAmpliada(alerta.imagen_url)}
                          className="w-full h-full object-cover opacity-80 cursor-pointer group-hover:opacity-100 group-hover:scale-105 transition-all duration-500"
                        />
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-300">
                           <span className="bg-black/70 text-white text-[10px] px-2 py-1 rounded border border-slate-600 backdrop-blur-sm">CLICK PARA AMPLIAR</span>
                        </div>
                        <div className="absolute bottom-1 right-1 bg-black/80 px-1.5 py-0.5 border border-slate-700 rounded-sm">
                          <span className="text-[8px] font-mono text-slate-400">EVIDENCIA</span>
                        </div>
                      </div>

                      <div className="bg-slate-900 border-l-2 border-red-500 p-2.5 rounded-r-sm">
                        <div className="flex items-center gap-1.5 mb-2">
                          <FileText size={12} className="text-slate-400" />
                          <span className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">Perfil Forense </span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed font-mono whitespace-pre-line">
                          {alerta.descripcion_ia || "Generando perfil forense desde la nube..."}
                        </p>
                      </div>
                    </div>
                  )}
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