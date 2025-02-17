using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.ServiceProcess;
using System.Threading.Tasks;
using Telegram.Bot;
using Newtonsoft.Json;
using System.Collections.Generic;

namespace CPUAlertService
{
    public partial class CPUAlertService : ServiceBase
    {
        private TelegramBotClient _bot;
        private string _chatId;
        private string _token;
        private int _cpuThreshold = 80;  // Umbral de CPU configurado para 80%, ajustable

        public CPUAlertService()
        {
            InitializeComponent();
        }

        protected override void OnStart(string[] args)
        {
            Log("Servicio iniciado.");
            Task.Run(() => MonitorCPU());
        }

        private async Task MonitorCPU()
        {
            try
            {
                Log("Iniciando monitoreo de CPU.");
                // Verifica si el archivo de configuración existe, si no, pide la configuración
                if (!File.Exists("config.json"))
                {
                    ConfigurarBot();
                }
                else
                {
                    CargarConfiguracion();
                }

                while (true)
                {
                    var cpuUsage = GetCPUUsage();
                    if (cpuUsage >= _cpuThreshold)
                    {
                        var message = await GenerateAlertMessage(cpuUsage);
                        await SendTelegramAlert(message);
                        Log($"Alerta enviada: {message}");
                    }
                    await Task.Delay(1000);  // Chequeo cada segundo para tener una respuesta más rápida
                }
            }
            catch (Exception ex)
            {
                Log($"Error: {ex.Message}");
            }
        }

        // Función para obtener el uso de CPU
        private float GetCPUUsage()
        {
            var cpuCounter = new PerformanceCounter("Processor", "% Processor Time", "_Total");
            cpuCounter.NextValue();  // Llamada inicial para obtener datos
            System.Threading.Thread.Sleep(1000);  // Esperar para obtener una lectura precisa
            return cpuCounter.NextValue();
        }

        // Función para obtener información del sistema (RAM, discos, procesos)
        private (string serverName, float totalRam, float usedRam, float freeRam, string diskInfo, string highCpuProcesses) GetSystemInfo()
        {
            var serverName = Environment.MachineName;
            var memory = new PerformanceCounter("Memory", "Available MBytes");
            float totalRam = new Microsoft.VisualBasic.Devices.ComputerInfo().TotalPhysicalMemory / (1024 * 1024 * 1024); // GB
            float freeRam = memory.NextValue() / 1024; // Convertir MB a GB
            float usedRam = totalRam - freeRam;

            string diskInfo = GetDiskInfo();
            string highCpuProcesses = GetHighCpuProcesses();

            return (serverName, totalRam, usedRam, freeRam, diskInfo, highCpuProcesses);
        }

        // Función para obtener información de los discos
        private string GetDiskInfo()
        {
            var diskInfo = "";
            foreach (var drive in DriveInfo.GetDrives())
            {
                if (drive.IsReady)
                {
                    var totalSpace = drive.TotalSize / (1024 * 1024 * 1024);  // GB
                    var freeSpace = drive.TotalFreeSpace / (1024 * 1024 * 1024);  // GB
                    diskInfo += $"{drive.Name}: {freeSpace} GB libres de {totalSpace} GB\n";
                }
            }
            return diskInfo;
        }

        // Función para obtener los procesos con mayor uso de CPU
        private string GetHighCpuProcesses()
        {
            string processesSummary = "";
            var processes = Process.GetProcesses();
            var highCpuProcesses = new List<(string name, float cpuUsage)>();

            foreach (var process in processes)
            {
                try
                {
                    var startTime = DateTime.UtcNow;
                    var startCpuUsage = process.TotalProcessorTime;
                    System.Threading.Thread.Sleep(500); // Esperar medio segundo
                    var endTime = DateTime.UtcNow;
                    var endCpuUsage = process.TotalProcessorTime;
                    var cpuUsedMs = (endCpuUsage - startCpuUsage).TotalMilliseconds;
                    var totalMsPassed = (endTime - startTime).TotalMilliseconds;
                    var cpuUsageTotal = cpuUsedMs / (Environment.ProcessorCount * totalMsPassed);

                    if (cpuUsageTotal > 0)
                    {
                        highCpuProcesses.Add((process.ProcessName, (float)cpuUsageTotal * 100));
                    }
                }
                catch { }
            }

            var topProcesses = highCpuProcesses.OrderByDescending(p => p.cpuUsage).Take(5);
            foreach (var proc in topProcesses)
            {
                processesSummary += $"{proc.name}: {proc.cpuUsage:F2}% de CPU\n";
            }

            return processesSummary;
        }

        // Función para generar el mensaje de alerta
        private async Task<string> GenerateAlertMessage(float cpuUsage)
        {
            var systemInfo = GetSystemInfo();

            var message = $"⚠️ *Alerta de alto uso de CPU en el servidor {systemInfo.serverName}* ⚠️\n" +
                          $"------------------------------------\n" +
                          $"*Nombre del Servidor:* {systemInfo.serverName}\n" +
                          $"*Carga actual del CPU:* {cpuUsage:.1f}%\n\n" +
                          $"*RAM Total:* {systemInfo.totalRam:.2f} GB\n" +
                          $"*RAM Usada:* {systemInfo.usedRam:.1f}%\n" +
                          $"*RAM Libre:* {systemInfo.freeRam:.2f} GB\n\n" +
                          $"*Estado de los discos:*\n{systemInfo.diskInfo}\n\n" +
                          $"*Procesos principales con mayor uso de CPU:*\n{(string.IsNullOrEmpty(systemInfo.highCpuProcesses) ? "Sin procesos destacados." : systemInfo.highCpuProcesses)}";

            return message;
        }

        // Función para enviar una alerta a Telegram
        private async Task SendTelegramAlert(string message)
        {
            try
            {
                await _bot.SendTextMessageAsync(_chatId, message, parseMode: Telegram.Bot.Types.Enums.ParseMode.Markdown);
            }
            catch (Exception ex)
            {
                Log($"Error enviando mensaje a Telegram: {ex.Message}");
            }
        }

        // Función para configurar el bot de Telegram y guardar la configuración
        private void ConfigurarBot()
        {
            Console.WriteLine("Bienvenido al sistema de Alert CPU.");
            Console.WriteLine("Desarrollado por el Área de Sistemas de Grupo Roma");
            Console.WriteLine("Por favor, configure los parámetros necesarios.");

            Console.WriteLine("Introduce el token de tu bot de Telegram:");
            _token = Console.ReadLine();

            Console.WriteLine("Introduce el ID de tu chat de Telegram:");
            _chatId = Console.ReadLine();

            Console.WriteLine("Introduce el umbral de CPU (por ejemplo, 80 para 80%):");
            _cpuThreshold = int.Parse(Console.ReadLine());

            // Guardar configuración en un archivo JSON
            var config = new BotConfig
            {
                Token = _token,
                ChatId = _chatId,
                CpuThreshold = _cpuThreshold
            };

            File.WriteAllText("config.json", JsonConvert.SerializeObject(config));
            _bot = new TelegramBotClient(_token);

            Console.WriteLine("Configuración guardada correctamente.");
        }

        // Cargar configuración desde archivo JSON
        private void CargarConfiguracion()
        {
            var config = JsonConvert.DeserializeObject<BotConfig>(File.ReadAllText("config.json"));
            _token = config.Token;
            _chatId = config.ChatId;
            _cpuThreshold = config.CpuThreshold;
            _bot = new TelegramBotClient(_token);
        }

        protected override void OnStop()
        {
            Log("Servicio detenido.");
        }

        private void Log(string message)
        {
            string logFilePath = "CPUAlertService.log";
            using (StreamWriter writer = new StreamWriter(logFilePath, true))
            {
                writer.WriteLine($"{DateTime.Now}: {message}");
            }
        }
    }

    // Clase para la configuración del bot
    public class BotConfig
    {
        public string Token { get; set; }
        public string ChatId { get; set; }
        public int CpuThreshold { get; set; }
    }

    class Program
    {
        static void Main(string[] args)
        {
            ServiceBase[] ServicesToRun;
            ServicesToRun = new ServiceBase[]
            {
                new CPUAlertService()
            };
            ServiceBase.Run(ServicesToRun);
        }
    }
}