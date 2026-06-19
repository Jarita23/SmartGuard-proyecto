import { useState } from 'react';
import { Shield, User, Lock } from 'lucide-react'; 
// CORREGIDO: Ahora apunta a tu archivo supabase.js real que está una carpeta más atrás (../)
import { supabase } from '../supabase'; 

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Conexión directa con la bóveda de Supabase
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setError('Credenciales denegadas. Verifique su identificación.');
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#050914] flex flex-col justify-center items-center p-4">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-red-900/10 blur-[120px] rounded-full pointer-events-none"></div>

      <div className="bg-[#0b101a] border border-gray-800/60 p-10 rounded-xl w-full max-w-md shadow-2xl z-10">
        
        <div className="flex flex-col items-center mb-10">
          <div className="bg-red-600/10 p-4 rounded-full border border-red-500/20 mb-4">
            <Shield className="w-10 h-10 text-red-600" strokeWidth={1.5} />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-widest">
            SMARTGUARD <span className="text-red-600">ACCESS</span>
          </h1>
          <p className="text-gray-500 text-xs tracking-[0.2em] mt-2 uppercase">
            Central de Monitoreo Restringida
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <label className="text-gray-400 text-xs font-semibold tracking-wider uppercase">
              Identificación Operador
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <User className="h-5 w-5 text-gray-500" />
              </div>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ej. central@smartguard.cl"
                className="w-full pl-10 pr-4 py-3 bg-[#050914] border border-gray-800 rounded-md text-gray-300 placeholder-gray-600 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/50 transition-all"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-gray-400 text-xs font-semibold tracking-wider uppercase">
              Clave de Acceso
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-500" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-3 bg-[#050914] border border-gray-800 rounded-md text-gray-300 placeholder-gray-600 focus:outline-none focus:border-red-500/50 focus:ring-1 focus:ring-red-500/50 transition-all"
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-500 text-sm p-3 rounded-md text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3.5 px-4 rounded-md tracking-wider text-sm transition-colors mt-4 shadow-[0_0_15px_rgba(220,38,38,0.3)]"
          >
            {loading ? 'VERIFICANDO...' : 'AUTORIZAR CONEXIÓN'}
          </button>
        </form>

        <div className="mt-8 text-center">
          <p className="text-gray-700 text-[10px] tracking-[0.3em] uppercase">
            Sistema Encriptado End-to-End
          </p>
        </div>
      </div>
    </div>
  );
}