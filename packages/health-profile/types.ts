/**
 * Attune.more - Unified Health Profile Types
 * Dört modülün paylaştığı merkezi kullanıcı ve sağlık geçmişi modelleri
 */

export interface ConsentSettings {
  cameraConsentGiven: boolean;
  microphoneConsentGiven: boolean;
  healthDataStorageConsentGiven: boolean;
  doctorSharingConsentGiven: boolean;
  consentTimestamp: string;
}

export interface UserProfile {
  id: string;
  displayName: string;
  truId: string;
  ageRange: '18-25' | '26-35' | '36-50' | '51-65' | '65+';
  preferredCity: string;
  preferredConsultationType: 'ALL' | 'IN_PERSON' | 'ONLINE';
  consent: ConsentSettings;
}

export interface VisionRecord {
  id: string;
  date: string;
  acuityRightLogMAR: number; // 0.0 = 20/20 Snellen (1.0)
  acuityLeftLogMAR: number;
  acuityRightSnellen: string; // "20/20" veya "1.0"
  acuityLeftSnellen: string;
  contrastSensitivityLogCS: number; // ör. 1.80 LogCS (normal: 1.65 - 1.95)
  calibratedDistanceCm: number;
  comparisonNote: string; // Tıbbi tanı içermeyen değişim notu
  ophthalmologistReferralRecommended: boolean;
}

export interface SkinRegionDetail {
  rednessScore: number; // 0-100 (CIELAB a* normalize)
  pigmentationScore: number; // 0-100 (L* & melanin eşdeğeri)
  textureVariance: number; // 0-100 (Laplacian gradient varyansı)
  changeFromBaselinePct: number; // +12% gibi değişim
}

export interface SkinRecord {
  id: string;
  date: string;
  regions: {
    forehead: SkinRegionDetail;
    rightCheek: SkinRegionDetail;
    leftCheek: SkinRegionDetail;
    nose: SkinRegionDetail;
    chin: SkinRegionDetail;
    periorbital: SkinRegionDetail; // Göz çevresi
  };
  overallComparisonNote: string;
  dermatologistReferralRecommended: boolean;
}

export type MentalMoodState = 'RELAXED' | 'FOCUSED' | 'TIRED' | 'STRESSED' | 'ANXIOUS';

export interface MentalSessionSummary {
  sessionId: string;
  date: string;
  durationSeconds: number;
  moodBefore: MentalMoodState;
  moodAfter: MentalMoodState;
  recurringThemes: string[]; // ör. ['uyku düzensizliği', 'iş stresi', 'yoğun tempo']
  summaryText: string;
  clinicalEscalationSuggested: boolean;
  suggestedActionNote?: string;
}

export interface AppointmentSlot {
  id: string;
  specialty: 'Dermatoloji' | 'Göz Hastalıkları' | 'Klinik Psikoloji';
  providerName: string;
  title: string;
  clinicName: string;
  locationLabel: string;
  isOnline: boolean;
  dateTime: string;
  displayTime: string;
  travelTimeMin: number;
  calendarConflict: boolean;
  bookingStatus: 'AVAILABLE' | 'PENDING_USER_CONFIRMATION' | 'CONFIRMED' | 'CANCELLED';
  bookingUrl?: string;
}

export interface ReferralContext {
  sourceModule: 'VISION' | 'SKIN' | 'MENTAL';
  reasonSummary: string;
  specialty: 'Dermatoloji' | 'Göz Hastalıkları' | 'Klinik Psikoloji' | string;
  timestamp: string;
  metricsSummary?: Record<string, any>;
}

export interface HealthProfile {
  user: UserProfile;
  visionHistory: VisionRecord[];
  skinHistory: SkinRecord[];
  mentalSessions: MentalSessionSummary[];
  activeReferrals: AppointmentSlot[];
  lastUpdated: string;
}

