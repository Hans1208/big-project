package com.aivle.bigproject.consultation;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConsultationRepository extends JpaRepository<Consultation, Long> {

    // 상담원은 자기가 담당한 상담만 본다 (ConsultationService.findAll 참고)
    List<Consultation> findByUserId(Long userId);
}
