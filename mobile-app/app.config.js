export default {
  expo: {
    name: "UruCheck IA",
    slug: "attendance-app",
    version: "1.0.0",
    sdkVersion: "55.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    updates: {
      url: "https://u.expo.dev/1eacb1c4-3e68-4b9b-a366-4f77847e3d37"
    },
    runtimeVersion: {
      policy: "appVersion"
    },
    android: {
      package: "com.empresa.attendance",
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#1e1e1e"
      },
      permissions: [
        "CAMERA",
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "VIBRATE"
      ]
    },
    ios: {
      bundleIdentifier: "com.empresa.attendance",
      infoPlist: {
        NSCameraUsageDescription: "Necesitamos acceso a la cámara para tomar una foto de validación al registrar tu asistencia.",
        NSLocationWhenInUseUsageDescription: "Necesitamos tu ubicación para confirmar que estás en el lugar de trabajo al registrar tu asistencia."
      }
    },
    plugins: [
      ["expo-camera", { cameraPermission: "Permitir acceso a la cámara para la verificación de asistencia." }],
      ["expo-location", { locationWhenInUsePermission: "Permitir acceso a la ubicación para confirmar tu lugar de trabajo." }]
    ],
    extra: {
      API_URL: process.env.EXPO_PUBLIC_API_URL || "https://asistencia.urufile.com/api",
      eas: {
        projectId: "1eacb1c4-3e68-4b9b-a366-4f77847e3d37"
      }
    }
  }
}
