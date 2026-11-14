"""Security awareness content: phishing, passwords, compliance (defensive training)."""


def phishing_awareness():
    """Return a concise anti-phishing training checklist."""
    return {
        'title': 'Concienciación anti-phishing',
        'red_flags': [
            'Remitente o dominio parecido al real (gogle.com, paypa1.com).',
            'Urgencia artificial: «tu cuenta será suspendida en 24h».',
            'Enlaces que no coinciden con el dominio mostrado (pasa el ratón, no hagas clic).',
            'Adjuntos inesperados (.zip, .exe, .html, macros de Office).',
            'Petición de credenciales, OTP, datos de tarjeta o «verificación de identidad».',
            'Saludo genérico («estimado cliente») y errores ortográficos.',
        ],
        'actions': [
            'Verifica el dominio real antes de hacer clic; escribe la URL a mano si hay duda.',
            'Nunca compartas contraseñas, códigos 2FA ni datos de tarjeta por correo o chat.',
            'Reporta el correo a seguridad@ tu organización y bórralo.',
            'Activa MFA en todas las cuentas importantes.',
            'Desconfía de facturas, entregas o problemas bancarios «urgentes».',
        ],
        'report_template': 'Asunto: Phishing sospechoso — Remitente: — Dominio: — Qué pedía: — ¿Hice clic? sí/no',
    }


def password_hygiene():
    """Return password best-practice guidance."""
    return {
        'title': 'Higiene de contraseñas',
        'rules': [
            'Mínimo 12-16 caracteres; mejor una frase memorable que una palabra con símbolos.',
            'Nunca reutilices contraseñas entre servicios; usa un gestor (Bitwarden, KeePass).',
            'Activa MFA siempre que exista; la contraseña sola no basta.',
            'No guardes contraseñas en texto plano, capturas ni notas del móvil.',
            'Revisa filtraciones en haveibeenpwned.com (o similar) periódicamente.',
            'En servidores: desactiva PasswordAuthentication en SSH y usa claves.',
        ],
    }


def compliance_checklist():
    """Map common defensive controls to ISO 27001 / NIST CSF themes."""
    return {
        'title': 'Checklist de cumplimiento (ISO 27001 / NIST CSF)',
        'identify': ['Inventario de activos y datos sensibles', 'Evaluación de riesgos documentada',
                     'Política de seguridad aprobada por dirección'],
        'protect': ['Control de acceso basado en roles', 'Cifrado en reposo y en tránsito',
                    'Política de contraseñas y MFA', 'Formación anti-phishing del personal'],
        'detect': ['Monitorización de logs (SIEM o journald centralizado)',
                   'Detección de intrusos (fail2ban, IDS)', 'Escaneos de vulnerabilidades periódicos'],
        'respond': ['Plan de respuesta a incidentes escrito y ensayado',
                    'Procedimiento de notificación de brechas', 'Capacidad de contener y erradicar'],
        'recover': ['Copias de seguridad probadas y aisladas', 'Plan de restauración con RTO/RPO definidos'],
        'note': 'Esto es una guía orientativa, no una certificación; para ISO 27001 formal se requiere auditoría externa.',
    }
