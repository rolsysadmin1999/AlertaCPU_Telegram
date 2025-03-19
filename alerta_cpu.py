import psutil
import time
import telegram
import tkinter as tk
from tkinter import messagebox
import threading
import asyncio
import socket
import logging

# Configurar logging
logging.basicConfig(filename='monitoreo.log', level=logging.INFO, format='%(asctime)s - %(message)s')

# Variable de control para detener la monitorización
detener_monitorizacion = False

# Variables para controlar el envío de alertas
ultima_alerta_ram = None
ultima_alerta_disco = None

# Función para enviar alerta
async def enviar_alerta(mensaje, bot, chat_ids):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=mensaje, parse_mode=telegram.constants.ParseMode.MARKDOWN)
            logging.info(f"Alerta enviada a {chat_id}: {mensaje}")
        except Exception as e:
            logging.error(f"Error al enviar alerta a {chat_id}: {e}")

# Función para obtener información del sistema
def obtener_info_sistema(monitor_cpu, monitor_ram, monitor_disk, cpu_threshold):
    mensaje = ""
    nombre_equipo = socket.gethostname()

    if monitor_cpu:
        uso_cpu = psutil.cpu_percent(interval=1)
        procesos = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), key=lambda p: p.info['cpu_percent'], reverse=True)[:5]
        mensaje += f"⚠️ *Alerta de alto uso de CPU en {nombre_equipo}!* ⚠️\n"
        mensaje += "------------------------------------\n"
        mensaje += f"*Carga actual del CPU:* {uso_cpu}%\n\n"
        mensaje += "*Procesos principales con mayor uso de CPU:*\n"
        for proc in procesos:
            mensaje += f"{proc.info['name']}: {proc.info['cpu_percent']}%\n"
        mensaje += "\n"

    if monitor_ram:
        ram = psutil.virtual_memory()
        if ram.percent > cpu_threshold:
            mensaje += f"⚠️ *Alerta de alto uso de RAM en {nombre_equipo}!* ⚠️\n"
            mensaje += "------------------------------------\n"
            mensaje += f"*RAM Total:* {ram.total / (1024 ** 3):.2f} GB\n"
            mensaje += f"*RAM Usada:* {ram.percent}%\n"
            mensaje += f"*RAM Libre:* {ram.available / (1024 ** 3):.2f} GB\n\n"

    if monitor_disk:
        discos = psutil.disk_partitions()
        uso_discos = [psutil.disk_usage(disk.mountpoint) for disk in discos]
        for disk, usage in zip(discos, uso_discos):
            if usage.percent > cpu_threshold:
                mensaje += f"⚠️ *Alerta de poco espacio en disco en {nombre_equipo}!* ⚠️\n"
                mensaje += "------------------------------------\n"
                mensaje += f"{disk.device} - Usado: {usage.used / (1024 ** 3):.2f} GB / Total: {usage.total / (1024 ** 3):.2f} GB / Libre: {usage.free / (1024 ** 3):.2f} GB\n"
                mensaje += "\n"

    return mensaje

# Función para monitorizar CPU
def monitorizar_cpu(bot, chat_ids, cpu_threshold, monitor_cpu, monitor_ram, monitor_disk):
    global detener_monitorizacion, ultima_alerta_ram, ultima_alerta_disco
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while not detener_monitorizacion:
        mensaje = ""
        if monitor_cpu:
            uso_cpu = psutil.cpu_percent(interval=1)
            logging.info(f"Uso de CPU actual: {uso_cpu}%")
            if uso_cpu > cpu_threshold:
                mensaje += obtener_info_sistema(monitor_cpu, False, False, cpu_threshold)
        if monitor_ram:
            ram = psutil.virtual_memory()
            if ram.percent > cpu_threshold and (ultima_alerta_ram is None or time.time() - ultima_alerta_ram > 3600):
                mensaje += obtener_info_sistema(False, monitor_ram, False, cpu_threshold)
                ultima_alerta_ram = time.time()
        if monitor_disk:
            discos = psutil.disk_partitions()
            uso_discos = [psutil.disk_usage(disk.mountpoint) for disk in discos]
            for disk, usage in zip(discos, uso_discos):
                if usage.percent > cpu_threshold and (ultima_alerta_disco is None or time.time() - ultima_alerta_disco > 3600):
                    mensaje += obtener_info_sistema(False, False, monitor_disk, cpu_threshold)
                    ultima_alerta_disco = time.time()
        if mensaje:
            loop.run_until_complete(enviar_alerta(mensaje, bot, chat_ids))
        time.sleep(5)  # Esperar 5 segundos antes de la siguiente comprobación

# Función para iniciar la monitorización en un hilo separado
def iniciar_monitorizacion(opcion):
    global detener_monitorizacion
    detener_monitorizacion = False
    chat_ids = entry_chat_ids.get().split(',')
    token = entry_token.get()
    cpu_threshold = int(entry_cpu_threshold.get()) if opcion == "CPU" else 0
    monitor_cpu = opcion == "CPU"
    monitor_ram = opcion == "RAM"
    monitor_disk = opcion == "Discos"

    logging.info(f"Iniciando monitorización con Chat IDs: {chat_ids}, Token: {token}, Umbral de CPU: {cpu_threshold}%, Monitor CPU: {monitor_cpu}, Monitor RAM: {monitor_ram}, Monitor Disk: {monitor_disk}")
    bot = telegram.Bot(token=token)
    hilo_monitorizacion = threading.Thread(target=monitorizar_cpu, args=(bot, chat_ids, cpu_threshold, monitor_cpu, monitor_ram, monitor_disk))
    hilo_monitorizacion.daemon = True
    hilo_monitorizacion.start()

    # Actualizar la etiqueta de monitoreo
    opciones_monitoreo = label_monitoreo.cget("text").replace("Se está monitoreando: ", "").replace(" ✅", "").split(", ")
    if "No se está monitoreando nada" in opciones_monitoreo:
        opciones_monitoreo.remove("No se está monitoreando nada")
    if opcion not in opciones_monitoreo:
        opciones_monitoreo.append(opcion)
    label_monitoreo.config(text=f"Se está monitoreando: {', '.join(opciones_monitoreo)} ✅")

    # Mostrar mensaje de información
    messagebox.showinfo("Bot Iniciado", f"El bot ha sido iniciado correctamente y está monitoreando el uso de {', '.join(opciones_monitoreo)}.")

# Función para detener la monitorización
def detener_monitorizacion_func():
    global detener_monitorizacion
    detener_monitorizacion = True
    logging.info("Monitorización detenida")
    messagebox.showinfo("Monitorización Detenida", "La monitorización ha sido detenida.")
    label_monitoreo.config(text="No se está monitoreando nada")

# Función para mostrar los campos de entrada
def mostrar_campos_entrada(opcion):
    frame_opciones.pack_forget()
    frame_entradas.pack(pady=10)
    if opcion == "CPU":
        tk.Label(frame_entradas, text="Umbral de CPU (%):").grid(row=2, column=0, sticky="e")
        entry_cpu_threshold.grid(row=2, column=1)
    else:
        entry_cpu_threshold.grid_remove()
    boton_iniciar.config(command=lambda: iniciar_monitorizacion(opcion))
    boton_iniciar.pack(pady=10)
    boton_detener.pack(pady=10)
    boton_volver.pack(pady=10)

# Función para volver al menú principal
def volver_menu_principal():
    frame_entradas.pack_forget()
    boton_iniciar.pack_forget()
    boton_detener.pack_forget()
    boton_volver.pack_forget()
    frame_opciones.pack(pady=10)

# Crear la interfaz gráfica
root = tk.Tk()
root.title("Bot de Alertas de Servidores")

# Configurar el tamaño de la ventana
root.geometry("400x400")

# Crear un marco para el título
frame_titulo = tk.Frame(root)
frame_titulo.pack(pady=10)

# Título principal
titulo = tk.Label(frame_titulo, text="Bot de Alertas de Servidores", font=("Helvetica", 16, "bold"))
titulo.pack()

# Subtítulo
subtitulo = tk.Label(frame_titulo, text="Grupo Roma\nDesarrollada por el área de Sistemas", font=("Helvetica", 10))
subtitulo.pack()

# Crear un marco para las opciones de monitoreo
frame_opciones = tk.Frame(root)
frame_opciones.pack(pady=10)

tk.Button(frame_opciones, text="Monitorear uso de CPU", command=lambda: mostrar_campos_entrada("CPU")).pack(anchor="w")
tk.Button(frame_opciones, text="Monitorear uso de RAM", command=lambda: mostrar_campos_entrada("RAM")).pack(anchor="w")
tk.Button(frame_opciones, text="Monitorear espacio en discos", command=lambda: mostrar_campos_entrada("Discos")).pack(anchor="w")

# Crear un marco para los campos de entrada
frame_entradas = tk.Frame(root)

tk.Label(frame_entradas, text="IDs del Chat (separados por comas):").grid(row=0, column=0, sticky="e")
entry_chat_ids = tk.Entry(frame_entradas, width=30)
entry_chat_ids.grid(row=0, column=1)

tk.Label(frame_entradas, text="Token del Bot:").grid(row=1, column=0, sticky="e")
entry_token = tk.Entry(frame_entradas, width=30)
entry_token.grid(row=1, column=1)

entry_cpu_threshold = tk.Entry(frame_entradas, width=30)

# Botón para iniciar la monitorización
boton_iniciar = tk.Button(root, text="Iniciar Monitorización", bg="green", fg="white")

# Botón para detener la monitorización
boton_detener = tk.Button(root, text="Detener Monitorización", command=detener_monitorizacion_func, bg="red", fg="white")

# Botón para volver al menú principal
boton_volver = tk.Button(root, text="Volver al Inicio", command=volver_menu_principal, bg="blue", fg="white")

# Etiqueta para mostrar qué se está monitoreando
label_monitoreo = tk.Label(root, text="No se está monitoreando nada", font=("Helvetica", 12))
label_monitoreo.pack(pady=10)

root.mainloop()