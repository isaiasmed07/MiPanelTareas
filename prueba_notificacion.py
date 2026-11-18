
from windows_toasts import Toast, WindowsToaster

toaster = WindowsToaster("Mi Panel de Tareas")

toast = Toast()
toast.text_fields = [
    "Mi Panel de Tareas",
    "¡Las notificaciones funcionan correctamente!"
]

toaster.show_toast(toast)

input("Presiona Enter para cerrar...")
