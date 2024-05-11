-- MySQL dump 10.13  Distrib 8.0.31, for macos12 (x86_64)
--
-- Host: 127.0.0.1    Database: ezllmtest_dev
-- ------------------------------------------------------
-- Server version	8.0.31

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tb_project_knowledge`
--

DROP TABLE IF EXISTS `tb_project_knowledge`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_knowledge` (
  `id` char(21) NOT NULL,
  `path` varchar(500) NOT NULL,
  PRIMARY KEY (`id`,`path`),
  CONSTRAINT `tb_project_knowledge_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_knowledge`
--

LOCK TABLES `tb_project_knowledge` WRITE;
/*!40000 ALTER TABLE `tb_project_knowledge` DISABLE KEYS */;
INSERT INTO `tb_project_knowledge` VALUES ('Ez1788916403366002688','static/projects/Ez1788916403366002688/knowledge/软件测试-缺陷轰炸和beta测试.pdf'),('Ez1788931757752451072','static/projects/Ez1788931757752451072/knowledge/软件测试-缺陷轰炸和beta测试.pdf');
/*!40000 ALTER TABLE `tb_project_knowledge` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_project_testdoc`
--

DROP TABLE IF EXISTS `tb_project_testdoc`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_project_testdoc` (
  `id` char(21) NOT NULL,
  `path` varchar(500) NOT NULL,
  PRIMARY KEY (`id`,`path`),
  CONSTRAINT `tb_project_testdoc_tb_test_project_null_fk` FOREIGN KEY (`id`) REFERENCES `tb_test_project` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_project_testdoc`
--

LOCK TABLES `tb_project_testdoc` WRITE;
/*!40000 ALTER TABLE `tb_project_testdoc` DISABLE KEYS */;
INSERT INTO `tb_project_testdoc` VALUES ('Ez1788916403366002688','static/projects/Ez1788916403366002688/testdoc/ProjectFiles.md'),('Ez1788916403366002688','static/projects/Ez1788916403366002688/testdoc/random_paragraph.doc'),('Ez1788916403366002688','static/projects/Ez1788916403366002688/testdoc/模拟业务1-机票订购系统.docx'),('Ez1788916403366002688','static/projects/Ez1788916403366002688/testdoc/软件测试-网站测试.pdf'),('Ez1788931757752451072','static/projects/Ez1788931757752451072/testdoc/random_paragraph.doc'),('Ez1788931757752451072','static/projects/Ez1788931757752451072/testdoc/README.md'),('Ez1788931757752451072','static/projects/Ez1788931757752451072/testdoc/模拟业务1-机票订购系统.docx'),('Ez1788931757752451072','static/projects/Ez1788931757752451072/testdoc/软件测试-网站测试.pdf');
/*!40000 ALTER TABLE `tb_project_testdoc` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tb_test_project`
--

DROP TABLE IF EXISTS `tb_test_project`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_test_project` (
  `id` char(21) NOT NULL COMMENT 'use snowflake method to generate unique id',
  `name` varchar(100) NOT NULL COMMENT 'project name',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='save the basic info of project to use llm to test';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_test_project`
--

LOCK TABLES `tb_test_project` WRITE;
/*!40000 ALTER TABLE `tb_test_project` DISABLE KEYS */;
INSERT INTO `tb_test_project` VALUES ('Ez1788916403366002688','testload'),('Ez1788931757752451072','testload-md');
/*!40000 ALTER TABLE `tb_test_project` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2024-05-11 11:32:01
