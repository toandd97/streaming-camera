import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, Pause, RefreshCw, AlertTriangle, Cpu, HardDrive, 
  WifiOff, Camera, Plus, Activity, TerminalSquare, 
  ServerCrash, ZapOff, Droplet, Bug, Skull
} from 'lucide-react';

const INITIAL_CAMERAS = [
  { id: 'cam-1', name: "Cam 1 (Main Gate)", url: "rtsp://mediamtx:8554/cam1", status: "CONNECTED", actualFps: 24, displayFps: 15, latency: 120, reconnects: 0, lastFrameTime: Date.now(), isHung: false },
  { id: 'cam-2', name: "Cam 2 (Parking)", url: "rtsp://mediamtx:8554/cam2", status: "CONNECTED", actualFps: 20, displayFps: 10, latency: 150, reconnects: 0, lastFrameTime: Date.now(), isHung: false },
  { id: 'cam-3', name: "Cam 3 (Warehouse)", url: "rtsp://mediamtx:8554/cam3", status: "CONNECTED", actualFps: 30, displayFps: 15, latency: 90, reconnects: 0, lastFrameTime: Date.now(), isHung: false },
  { id: 'cam-4', name: "Cam 4 (Office)", url: "rtsp://mediamtx:8554/cam4", status: "CONNECTED", actualFps: 25, displayFps: 5, latency: 110, reconnects: 0, lastFrameTime: Date.now(), isHung: false },
];

const METRICS_INITIAL = { cpu: 25, ram: 45, gpu: false };
const NO_FRAME_TIMEOUT = 5000; 

export default function App() {
  const [cameras, setCameras] = useState(INITIAL_CAMERAS);
  const [systemMetrics, setSystemMetrics] = useState(METRICS_INITIAL);
  const [events, setEvents] = useState([
    { id: `evt-init-${Date.now()}`, time: new Date().toLocaleTimeString(), type: 'INFO', message: 'System started. MediaMTX and Backend initialized.' }
  ]);
  
  // Fault Injection States
  const [cpuSpike, setCpuSpike] = useState(false);
  const [memoryLeak, setMemoryLeak] = useState(false);
  const [networkJitter, setNetworkJitter] = useState(false);
  const [mediaMtxCrashed, setMediaMtxCrashed] = useState(false);

  const camerasRef = useRef(cameras);
  const systemMetricsRef = useRef(systemMetrics);

  useEffect(() => { camerasRef.current = cameras; }, [cameras]);
  useEffect(() => { systemMetricsRef.current = systemMetrics; }, [systemMetrics]);

  // Helper to add log event manually
  const addEvent = (type, message) => {
    const uniqueId = `evt-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    setEvents(prev => [{ id: uniqueId, time: new Date().toLocaleTimeString(), type, message }, ...prev].slice(0, 80));
  };

  useEffect(() => {
    const workerLoop = setInterval(() => {
      const now = Date.now();
      const currentCameras = camerasRef.current;
      const nextCameras = [];
      const newEvents = [];
      
      for (const cam of currentCameras) {
        let { status: newStatus, reconnects: newReconnects, actualFps: newActualFps, latency: newLatency, lastFrameTime, isHung } = cam;

        // FAULT: MediaMTX Crashed
        if (mediaMtxCrashed) {
          if (cam.status !== "ERROR") {
            newEvents.push({ type: "ERROR", message: `Camera [${cam.name}] Connection Refused! MediaMTX is down.` });
          }
          nextCameras.push({ ...cam, status: "ERROR", actualFps: 0, latency: 0 });
          continue;
        }
        
        // Recover from Server Crash
        if (cam.status === "ERROR" && !mediaMtxCrashed) {
            newStatus = "RECONNECTING";
            newEvents.push({ type: "INFO", message: `MediaMTX restored. Worker [${cam.name}] attempting reconnect...` });
        }

        // FAULT: Decoder Hang (Thread block simulation)
        if (isHung) {
            newLatency += 1000;
            newActualFps = 0;
            if (newLatency === 3000) newEvents.push({ type: "WARNING", message: `Camera [${cam.name}] thread seems blocked. High latency...` });
            if (newLatency > 6000) {
                newEvents.push({ type: "CRITICAL", message: `Camera [${cam.name}] Worker Hang Detected! Forcing thread kill & restart.` });
                nextCameras.push({ ...cam, status: "DISCONNECTED", isHung: false, lastFrameTime: 0 });
                continue;
            }
            nextCameras.push({ ...cam, latency: newLatency, actualFps: newActualFps, status: newStatus });
            continue;
        }

        // NORMAL STATE MACHINE LOGIC
        if (cam.status === "CONNECTED" && (now - cam.lastFrameTime > NO_FRAME_TIMEOUT)) {
          newStatus = "DISCONNECTED";
          newActualFps = 0;
          newEvents.push({ type: "ERROR", message: `Camera [${cam.name}] NO_FRAME_TIMEOUT (>5s). Stream lost.` });
        } 
        else if (cam.status === "DISCONNECTED") {
          newStatus = "RECONNECTING";
          newReconnects += 1;
          newEvents.push({ type: "WARNING", message: `Camera [${cam.name}] attempting to reconnect... (Count: ${newReconnects})` });
        }
        else if (cam.status === "RECONNECTING") {
          // 40% chance to reconnect successfully in simulation
          if (Math.random() > 0.6) {
             newStatus = "CONNECTED";
             lastFrameTime = now;
             newActualFps = 20 + Math.floor(Math.random() * 10);
             newEvents.push({ type: "SUCCESS", message: `Camera [${cam.name}] reconnected successfully!` });
          }
        }
        else if (cam.status === "CONNECTED") {
             // FAULT: Network Jitter
             if (networkJitter) {
                 newActualFps = Math.max(1, Math.floor(cam.actualFps * 0.5)); // Drop FPS
                 newLatency = Math.min(2000, cam.latency + 300 + Math.random() * 500); // Spike latency
                 if (Math.random() > 0.8) newEvents.push({ type: "WARNING", message: `LOW_FPS Alert on [${cam.name}]: FPS dropped to ${newActualFps}` });
             } else {
                 newActualFps = Math.max(15, Math.min(30, cam.actualFps + (Math.random() > 0.5 ? 1 : -1)));
                 newLatency = Math.max(50, Math.min(300, cam.latency + (Math.random() > 0.5 ? 10 : -10)));
             }
             lastFrameTime = now;
        }

        nextCameras.push({ ...cam, status: newStatus, reconnects: newReconnects, actualFps: newActualFps, latency: newLatency, lastFrameTime });
      }

      setCameras(nextCameras);
      
      // Batch update events outside of the camera state updater
      if (newEvents.length > 0) {
          setEvents(prev => {
              const evtObjects = newEvents.map(e => ({
                  id: `evt-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                  time: new Date().toLocaleTimeString(),
                  type: e.type,
                  message: e.message
              }));
              return [...evtObjects, ...prev].slice(0, 80);
          });
      }
    }, 1000); 

    return () => clearInterval(workerLoop);
  }, [mediaMtxCrashed, networkJitter]);

  useEffect(() => {
    const metricsLoop = setInterval(() => {
      const prev = systemMetricsRef.current;
      const newEvents = [];
      
      // CPU LOGIC
      const newCpu = cpuSpike ? Math.min(100, prev.cpu + 15) : Math.max(15, Math.min(40, prev.cpu + (Math.random() * 10 - 5)));
      if (newCpu > 90 && prev.cpu <= 90) newEvents.push({ type: "CRITICAL", message: "HIGH CPU ALERT (>90%). Processing lag detected." });

      // RAM LOGIC (Memory Leak Simulation)
      let newRam = prev.ram;
      if (memoryLeak) {
          newRam = Math.min(100, prev.ram + 5);
          if (newRam >= 85 && prev.ram < 85) newEvents.push({ type: "CRITICAL", message: "HIGH MEMORY ALERT (>85%). Possible Memory Leak in Decoder!" });
          if (newRam === 100 && prev.ram < 100) {
              newEvents.push({ type: "CRITICAL", message: "☠️ OOM KILLED: System ran out of memory. Restarting Backend Service..." });
              setTimeout(() => {
                  setSystemMetrics(METRICS_INITIAL);
                  setMemoryLeak(false);
                  addEvent("INFO", "Backend Service Restarted successfully.");
              }, 3000);
          }
      } else {
          newRam = Math.max(30, Math.min(60, prev.ram + (Math.random() * 4 - 2))); // Normal fluctuation
      }

      setSystemMetrics({ ...prev, cpu: Math.round(newCpu), ram: Math.round(newRam) });
      
      if (newEvents.length > 0) {
          setEvents(prevEv => {
              const evtObjects = newEvents.map(e => ({
                  id: `evt-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                  time: new Date().toLocaleTimeString(),
                  type: e.type,
                  message: e.message
              }));
              return [...evtObjects, ...prevEv].slice(0, 80);
          });
      }
    }, 1500);
    return () => clearInterval(metricsLoop);
  }, [cpuSpike, memoryLeak]);

  const simulateDisconnect = (id) => {
    const cam = cameras.find(c => c.id === id);
    if (cam) addEvent("INFO", `Simulating FFmpeg death for [${cam.name}].`);
    
    setCameras(prev => prev.map(c => 
      c.id === id ? { ...c, lastFrameTime: Date.now() - NO_FRAME_TIMEOUT - 1000 } : c
    ));
  };

  const simulateHang = (id) => {
      const cam = cameras.find(c => c.id === id);
      if (cam) addEvent("WARNING", `Injected Bug: Thread for [${cam.name}] frozen.`);

      setCameras(prev => prev.map(c => 
        c.id === id ? { ...c, isHung: true } : c
      ));
  };

  const updateDisplayFps = (id, fps) => {
    setCameras(prev => prev.map(c => c.id === id ? { ...c, displayFps: parseInt(fps) } : c));
  };

  const registerNewCamera = () => {
      const newId = `cam-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      const newCamIndex = cameras.length + 1;
      const newCam = {
          id: newId, name: `Cam ${newCamIndex} (New)`, url: `rtsp://mediamtx:8554/cam${newCamIndex}`,
          status: "CREATED", actualFps: 0, displayFps: 10, latency: 0, reconnects: 0, lastFrameTime: Date.now(), isHung: false
      };
      setCameras([...cameras, newCam]);
      addEvent("INFO", `Registered new camera: ${newCam.name}`);
      
      setTimeout(() => {
          setCameras(prev => prev.map(c => c.id === newId ? { ...c, status: "CONNECTING" } : c));
          addEvent("INFO", `StreamWorker started for [${newCam.name}]. Connecting...`);
          setTimeout(() => {
               setCameras(prev => prev.map(c => c.id === newId ? { ...c, status: "CONNECTED", actualFps: 25, latency: 100, lastFrameTime: Date.now() } : c));
          }, 2000);
      }, 1000);
  };

  const getStatusColor = (status) => {
    switch(status) {
      case 'CONNECTED': return 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]';
      case 'DISCONNECTED': return 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]';
      case 'RECONNECTING': return 'bg-orange-500 animate-pulse';
      case 'CONNECTING': return 'bg-blue-500 animate-pulse';
      case 'ERROR': return 'bg-red-700 animate-bounce';
      case 'CREATED': return 'bg-gray-400';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans p-4 md:p-6 flex flex-col gap-6">
      
      {/* HEADER */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-xl">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-white">
            <Camera className="text-blue-400" />
            VMS Logic Simulator
          </h1>
          <p className="text-sm text-slate-400 mt-1">Backend Test B1 - Operations & Chaos Engineering</p>
        </div>

        {/* METRICS */}
        <div className="flex gap-4">
          <div className="flex items-center gap-2 bg-slate-950 px-4 py-2 rounded-lg border border-slate-800">
            <Cpu className={systemMetrics.cpu > 80 ? "text-red-400 animate-pulse" : "text-emerald-400"} size={18} />
            <span className="font-mono text-sm">CPU: <span className={systemMetrics.cpu > 80 ? "text-red-400 font-bold" : ""}>{systemMetrics.cpu}%</span></span>
          </div>
          <div className="flex items-center gap-2 bg-slate-950 px-4 py-2 rounded-lg border border-slate-800">
            <HardDrive className={systemMetrics.ram > 85 ? "text-red-400 animate-pulse" : "text-blue-400"} size={18} />
            <span className="font-mono text-sm">RAM: <span className={systemMetrics.ram > 85 ? "text-red-400 font-bold" : ""}>{systemMetrics.ram}%</span></span>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT GRID */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        
        {/* LEFT PANEL: CAMERA STREAMS */}
        <div className="xl:col-span-3 space-y-4">
            <div className="flex justify-between items-center">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Activity size={20}/> Camera Streams (Live Preview)
                </h2>
                <button onClick={registerNewCamera} className="flex items-center gap-1 bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-all shadow-lg hover:shadow-blue-500/20">
                    <Plus size={16} /> Register Camera
                </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cameras.map((cam) => (
                <div key={cam.id} className={`bg-slate-900 rounded-xl overflow-hidden border transition-colors shadow-lg flex flex-col relative
                     ${cam.isHung ? 'border-yellow-500/50' : cam.status === 'ERROR' ? 'border-red-600/50' : 'border-slate-800'}`}>
                
                {/* Video Area */}
                <div className="relative h-48 bg-black flex items-center justify-center overflow-hidden">
                    {cam.status === "CONNECTED" && !cam.isHung ? (
                        <div className="absolute inset-0 opacity-30 bg-[url('https://images.unsplash.com/photo-1557597774-9d273605dfa9?auto=format&fit=crop&w=800&q=80')] bg-cover bg-center" 
                             style={{ animation: `pulse ${networkJitter ? 2 : 1/cam.displayFps}s infinite alternate ${networkJitter ? 'steps(2)' : 'linear'}` }}></div>
                    ) : cam.isHung ? (
                        <div className="absolute inset-0 opacity-20 bg-[url('https://images.unsplash.com/photo-1557597774-9d273605dfa9?auto=format&fit=crop&w=800&q=80')] bg-cover bg-center grayscale filter blur-sm"></div>
                    ) : (
                         <div className="text-slate-600 flex flex-col items-center z-10">
                            {cam.status === 'ERROR' ? <ServerCrash size={32} className="mb-2 text-red-500"/> : <WifiOff size={32} className="mb-2" />}
                            <span className="font-mono text-sm tracking-widest">{cam.status === 'ERROR' ? 'SERVER UNREACHABLE' : 'NO SIGNAL'}</span>
                         </div>
                    )}

                    {cam.isHung && <div className="absolute inset-0 flex items-center justify-center text-yellow-500 font-bold tracking-widest z-10 animate-pulse bg-black/50 backdrop-blur-sm">THREAD HUNG</div>}

                    {/* Status Badge */}
                    <div className="absolute top-3 left-3 flex items-center gap-2 bg-slate-950/80 backdrop-blur-sm px-2.5 py-1 rounded-md text-xs font-semibold border border-slate-700/50 z-20">
                        <span className={`w-2.5 h-2.5 rounded-full ${getStatusColor(cam.status)}`}></span>
                        {cam.status}
                    </div>

                    {/* Source FPS Badge */}
                    <div className={`absolute top-3 right-3 bg-slate-950/80 backdrop-blur-sm px-2 py-1 rounded-md text-xs font-mono border z-20
                                  ${cam.actualFps < 10 && cam.status === 'CONNECTED' ? 'text-orange-400 border-orange-500/50' : 'text-white border-slate-700/50'}`}>
                        {cam.actualFps} FPS {networkJitter && cam.status === 'CONNECTED' && <span className="text-red-500 ml-1">↓</span>}
                    </div>
                </div>

                {/* Controls & Metrics Area */}
                <div className="p-4 bg-slate-900 border-t border-slate-800">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="font-medium text-slate-100 truncate pr-2">{cam.name}</h3>
                        
                        <div className="flex gap-2">
                            <button onClick={() => simulateHang(cam.id)} disabled={cam.status !== "CONNECTED" || cam.isHung}
                                className="text-[10px] bg-yellow-900/30 text-yellow-400 hover:bg-yellow-900/60 disabled:opacity-30 px-2 py-1.5 rounded transition-colors flex items-center gap-1 border border-yellow-700/30">
                                <Bug size={12} /> Hang Worker
                            </button>
                            <button onClick={() => simulateDisconnect(cam.id)} disabled={cam.status !== "CONNECTED"}
                                className="text-[10px] bg-red-900/30 text-red-400 hover:bg-red-900/60 disabled:opacity-30 px-2 py-1.5 rounded transition-colors flex items-center gap-1 border border-red-700/30">
                                <Pause size={12} /> Kill Stream
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-xs text-slate-400">
                        <div className="flex justify-between items-center">
                            <span>Latency:</span>
                            <span className={`font-mono ${cam.latency > 1000 ? 'text-red-400 font-bold animate-pulse' : 'text-slate-200'}`}>
                                {cam.status === 'CONNECTED' || cam.isHung ? `${cam.latency}ms` : '---'}
                            </span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span>Display FPS:</span>
                            <select value={cam.displayFps} onChange={(e) => updateDisplayFps(cam.id, e.target.value)}
                                className="bg-slate-950 border border-slate-700 text-slate-200 rounded px-1.5 py-0.5 outline-none font-mono focus:border-blue-500 transition-colors">
                                <option value="1">1</option><option value="5">5</option><option value="10">10</option><option value="15">15</option><option value="30">30</option>
                            </select>
                        </div>
                        <div className="flex justify-between items-center">
                            <span>Reconnects:</span>
                            <span className="font-mono text-orange-300 bg-orange-900/20 px-1.5 py-0.5 rounded">{cam.reconnects}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span>Protocol:</span>
                            <span className="font-mono text-slate-500">RTSP/TCP</span>
                        </div>
                    </div>
                </div>
                </div>
            ))}
            </div>
        </div>

        {/* RIGHT PANEL: LOGS & CHAOS CONTROLS */}
        <div className="space-y-4 flex flex-col h-[calc(100vh-140px)]">
            
            {/* Chaos Engineering Panel */}
            <div className="bg-slate-900 p-4 rounded-xl border border-red-900/30 shadow-lg relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-600 via-orange-500 to-red-600"></div>
                <h2 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2 uppercase tracking-wider">
                    <Skull size={16} className="text-red-400"/> Chaos Engineering
                </h2>
                
                <div className="grid grid-cols-2 gap-2">
                    <button onMouseDown={() => setCpuSpike(true)} onMouseUp={() => setCpuSpike(false)} onMouseLeave={() => setCpuSpike(false)}
                        className="bg-slate-800 hover:bg-slate-700 text-left px-2 py-2 rounded border border-slate-700 flex flex-col gap-1 transition-colors group">
                        <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1"><Cpu size={12}/> Spike CPU</span>
                        <span className="text-[9px] text-slate-500 group-hover:text-slate-400">(Hold to trigger)</span>
                    </button>
                    
                    <button onClick={() => setMemoryLeak(!memoryLeak)}
                        className={`text-left px-2 py-2 rounded border flex flex-col gap-1 transition-colors ${memoryLeak ? 'bg-red-900/40 border-red-500/50' : 'bg-slate-800 hover:bg-slate-700 border-slate-700'}`}>
                        <span className={`text-[11px] font-semibold flex items-center gap-1 ${memoryLeak ? 'text-red-400' : 'text-slate-300'}`}><Droplet size={12}/> Mem Leak</span>
                        <span className="text-[9px] text-slate-500">{memoryLeak ? '(OOM incoming...)' : '(Toggle)'}</span>
                    </button>

                    <button onClick={() => setNetworkJitter(!networkJitter)}
                        className={`text-left px-2 py-2 rounded border flex flex-col gap-1 transition-colors ${networkJitter ? 'bg-yellow-900/40 border-yellow-500/50' : 'bg-slate-800 hover:bg-slate-700 border-slate-700'}`}>
                        <span className={`text-[11px] font-semibold flex items-center gap-1 ${networkJitter ? 'text-yellow-400' : 'text-slate-300'}`}><ZapOff size={12}/> Jitter</span>
                        <span className="text-[9px] text-slate-500">{networkJitter ? '(High Latency)' : '(Toggle)'}</span>
                    </button>

                    <button onClick={() => setMediaMtxCrashed(!mediaMtxCrashed)}
                        className={`text-left px-2 py-2 rounded border flex flex-col gap-1 transition-colors ${mediaMtxCrashed ? 'bg-red-900/40 border-red-500/50' : 'bg-slate-800 hover:bg-slate-700 border-slate-700'}`}>
                        <span className={`text-[11px] font-semibold flex items-center gap-1 ${mediaMtxCrashed ? 'text-red-400' : 'text-slate-300'}`}><ServerCrash size={12}/> MediaMTX</span>
                        <span className="text-[9px] text-slate-500">{mediaMtxCrashed ? '(Server Down)' : '(Crash Server)'}</span>
                    </button>
                </div>
            </div>

            {/* Event Logs */}
            <div className="bg-slate-900 rounded-xl border border-slate-800 shadow-lg flex-1 flex flex-col overflow-hidden">
                <div className="p-3 bg-slate-950/50 border-b border-slate-800 flex justify-between items-center">
                    <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                        <TerminalSquare size={16} className="text-slate-400"/> System Events Log
                    </h2>
                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded-full text-slate-400">Live</span>
                </div>
                <div className="p-3 flex-1 overflow-y-auto space-y-2.5 font-mono text-[11px] leading-relaxed custom-scrollbar">
                    {events.map((ev) => (
                        <div key={ev.id} className="flex gap-2">
                            <span className="text-slate-600 shrink-0">[{ev.time}]</span>
                            <span className={`break-words w-full
                                ${ev.type === 'INFO' ? 'text-blue-300' : ''}
                                ${ev.type === 'SUCCESS' ? 'text-emerald-400' : ''}
                                ${ev.type === 'WARNING' ? 'text-yellow-400' : ''}
                                ${ev.type === 'ERROR' ? 'text-red-400' : ''}
                                ${ev.type === 'CRITICAL' ? 'text-red-100 font-bold bg-red-900/60 border border-red-500/30 px-1.5 py-0.5 rounded shadow-sm' : ''}
                            `}>
                                {ev.message}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

        </div>
      </div>

        {}
        <style dangerouslySetInnerHTML={{__html: `
            .custom-scrollbar::-webkit-scrollbar { width: 6px; }
            .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
            .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #475569; }
        `}} />
    </div>
  );
}