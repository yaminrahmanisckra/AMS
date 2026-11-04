import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class AppColors {
  static const navy = Color(0xFF10243F);
  static const navyDeep = Color(0xFF0B1B30);
  static const teal = Color(0xFF0F766E);
  static const tealDeep = Color(0xFF0B5E56);
  static const gold = Color(0xFFD4A017);
  static const goldSoft = Color(0xFFFFF6DC);
  static const cream = Color(0xFFF6F1E7);
  static const ink = Color(0xFF1C2430);
  static const muted = Color(0xFF5E6A75);
  static const card = Color(0xFFFFFFFF);
  static const coral = Color(0xFFC2410C);
  static const indigo = Color(0xFF3730A3);
  static const rose = Color(0xFF9F1239);
  static const blue = Color(0xFF1D4E89);
  static const line = Color(0xFFE6DCC8);

  static const accents = <Color>[
    teal,
    blue,
    coral,
    indigo,
    rose,
    Color(0xFF0369A1),
    Color(0xFF7C3AED),
  ];
}

ThemeData buildAppTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.teal,
    primary: AppColors.teal,
    onPrimary: Colors.white,
    secondary: AppColors.gold,
    surface: AppColors.cream,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.cream,
    appBarTheme: const AppBarTheme(
      systemOverlayStyle: SystemUiOverlayStyle.light,
      backgroundColor: Colors.transparent,
      foregroundColor: Colors.white,
      elevation: 0,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.navy,
      contentTextStyle: const TextStyle(color: Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFFFBF8F2),
      labelStyle: const TextStyle(color: AppColors.muted),
      hintStyle: const TextStyle(color: AppColors.muted),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.teal, width: 1.6),
      ),
    ),
  );
}
