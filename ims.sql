-- MySQL dump 10.13  Distrib 8.0.27, for Linux (x86_64)
--
-- Host: localhost    Database: ims
-- ------------------------------------------------------
-- Server version	8.0.27

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
-- Table structure for table `category`
--

DROP TABLE IF EXISTS `category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `category` (
  `category_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `superior_category` varchar(20) NOT NULL,
  `accessory_for` varchar(20) DEFAULT NULL,
  `spare_part_for` varchar(20) NOT NULL,
  `legal_descr` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`category_id`)
) ENGINE=InnoDB AUTO_INCREMENT=67 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `customer`
--

DROP TABLE IF EXISTS `customer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `customer` (
  `customer_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(100) DEFAULT NULL,
  `phone_number` varchar(50) NOT NULL,
  `address` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`customer_id`)
) ENGINE=InnoDB AUTO_INCREMENT=53 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `item`
--

DROP TABLE IF EXISTS `item`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `item` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) DEFAULT NULL,
  `amount` int DEFAULT NULL,
  `description` varchar(5000) DEFAULT NULL,
  `price` int DEFAULT NULL,
  `internal` int NOT NULL,
  `state` varchar(20) NOT NULL,
  `check_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `edit_date` datetime DEFAULT NULL,
  `id_checked_by` int DEFAULT NULL,
  `id_edited_by` int DEFAULT NULL,
  `id_category` int NOT NULL,
  `id_warehouse` int DEFAULT NULL,
  `id_repair` int DEFAULT NULL,
  `id_purchase` int DEFAULT NULL,
  `id_sale` int DEFAULT NULL,
  `id_online_upload` int DEFAULT NULL,
  `serial_number` varchar(25) DEFAULT NULL,
  PRIMARY KEY (`item_id`),
  KEY `id_repair` (`id_repair`),
  KEY `id_online_upload` (`id_online_upload`),
  KEY `id_checked_by` (`id_checked_by`),
  KEY `id_edited_by` (`id_edited_by`),
  KEY `id_sale` (`id_sale`),
  KEY `id_warehouse` (`id_warehouse`),
  KEY `id_category` (`id_category`),
  CONSTRAINT `item_ibfk_1` FOREIGN KEY (`id_repair`) REFERENCES `repair` (`repair_id`) ON DELETE SET NULL,
  CONSTRAINT `item_ibfk_2` FOREIGN KEY (`id_online_upload`) REFERENCES `online_upload` (`online_upload_id`) ON DELETE SET NULL,
  CONSTRAINT `item_ibfk_3` FOREIGN KEY (`id_checked_by`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `item_ibfk_4` FOREIGN KEY (`id_edited_by`) REFERENCES `user` (`user_id`) ON DELETE SET NULL,
  CONSTRAINT `item_ibfk_5` FOREIGN KEY (`id_sale`) REFERENCES `sale` (`sale_id`) ON DELETE SET NULL,
  CONSTRAINT `item_ibfk_6` FOREIGN KEY (`id_warehouse`) REFERENCES `warehouse` (`warehouse_id`) ON DELETE SET NULL,
  CONSTRAINT `item_ibfk_7` FOREIGN KEY (`id_category`) REFERENCES `category` (`category_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1029 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `online_upload`
--

DROP TABLE IF EXISTS `online_upload`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `online_upload` (
  `online_upload_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `price` decimal(15,2) NOT NULL,
  `description` varchar(5000) DEFAULT NULL,
  `date` datetime DEFAULT CURRENT_TIMESTAMP,
  `id_shop_category` int DEFAULT NULL,
  `id_shop_order` int DEFAULT NULL,
  `id_sale` int DEFAULT NULL,
  PRIMARY KEY (`online_upload_id`),
  KEY `id_shop_category` (`id_shop_category`),
  KEY `id_shop_order` (`id_shop_order`),
  KEY `id_sale` (`id_sale`),
  CONSTRAINT `online_upload_ibfk_1` FOREIGN KEY (`id_shop_category`) REFERENCES `shop_category` (`shop_category_id`),
  CONSTRAINT `online_upload_ibfk_2` FOREIGN KEY (`id_shop_order`) REFERENCES `shop_order` (`shop_order_id`),
  CONSTRAINT `online_upload_ibfk_3` FOREIGN KEY (`id_sale`) REFERENCES `sale` (`sale_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `purchase`
--

DROP TABLE IF EXISTS `purchase`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `purchase` (
  `purchase_id` int NOT NULL AUTO_INCREMENT,
  `supplier` varchar(50) DEFAULT NULL,
  `price` varchar(100) NOT NULL,
  `id_created_by` int NOT NULL,
  `date` datetime DEFAULT CURRENT_TIMESTAMP,
  `identifier` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`purchase_id`),
  KEY `id_created_by` (`id_created_by`),
  CONSTRAINT `purchase_ibfk_1` FOREIGN KEY (`id_created_by`) REFERENCES `user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `repair`
--

DROP TABLE IF EXISTS `repair`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `repair` (
  `repair_id` int NOT NULL AUTO_INCREMENT,
  `state` varchar(20) NOT NULL,
  `description` varchar(1000) DEFAULT NULL,
  `edit_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `id_edited_by` int NOT NULL,
  `id_repair_order` int DEFAULT NULL,
  `price` decimal(15,2) DEFAULT NULL,
  PRIMARY KEY (`repair_id`),
  KEY `id_edited_by` (`id_edited_by`),
  KEY `id_repair_order` (`id_repair_order`),
  CONSTRAINT `repair_ibfk_1` FOREIGN KEY (`id_edited_by`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `repair_ibfk_2` FOREIGN KEY (`id_repair_order`) REFERENCES `repair_order` (`repair_order_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=52 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `repair_order`
--

DROP TABLE IF EXISTS `repair_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `repair_order` (
  `repair_order_id` int NOT NULL AUTO_INCREMENT,
  `state` varchar(20) NOT NULL,
  `description` varchar(1000) DEFAULT NULL,
  `issue_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `id_edited_by` int NOT NULL,
  `edit_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `delivery_date` datetime DEFAULT NULL,
  `id_customer` int NOT NULL,
  `id_sale` int DEFAULT NULL,
  `id_item` int DEFAULT NULL,
  `id_service` int DEFAULT NULL,
  PRIMARY KEY (`repair_order_id`),
  KEY `id_item` (`id_item`),
  KEY `id_edited_by` (`id_edited_by`),
  KEY `id_customer` (`id_customer`),
  KEY `id_sale` (`id_sale`),
  KEY `id_service` (`id_service`),
  CONSTRAINT `repair_order_ibfk_1` FOREIGN KEY (`id_item`) REFERENCES `item` (`item_id`) ON DELETE SET NULL,
  CONSTRAINT `repair_order_ibfk_2` FOREIGN KEY (`id_edited_by`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `repair_order_ibfk_3` FOREIGN KEY (`id_customer`) REFERENCES `customer` (`customer_id`) ON DELETE CASCADE,
  CONSTRAINT `repair_order_ibfk_4` FOREIGN KEY (`id_sale`) REFERENCES `sale` (`sale_id`) ON DELETE SET NULL,
  CONSTRAINT `repair_order_ibfk_5` FOREIGN KEY (`id_service`) REFERENCES `service` (`service_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=71 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sale`
--

DROP TABLE IF EXISTS `sale`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sale` (
  `sale_id` int NOT NULL AUTO_INCREMENT,
  `description` varchar(5000) DEFAULT NULL,
  `price` varchar(100) NOT NULL,
  `id_created_by` int NOT NULL,
  `date` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`sale_id`),
  KEY `id_created_by` (`id_created_by`),
  CONSTRAINT `sale_ibfk_1` FOREIGN KEY (`id_created_by`) REFERENCES `user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `service`
--

DROP TABLE IF EXISTS `service`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `service` (
  `service_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) DEFAULT NULL,
  `description` varchar(500) DEFAULT NULL,
  `price` decimal(15,2) DEFAULT NULL,
  PRIMARY KEY (`service_id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `shop_category`
--

DROP TABLE IF EXISTS `shop_category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shop_category` (
  `shop_category_id` int NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`shop_category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `shop_order`
--

DROP TABLE IF EXISTS `shop_order`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shop_order` (
  `shop_order_id` int NOT NULL AUTO_INCREMENT,
  `state` varchar(20) DEFAULT NULL,
  `date_completed` datetime DEFAULT NULL,
  PRIMARY KEY (`shop_order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `spare_part`
--

DROP TABLE IF EXISTS `spare_part`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `spare_part` (
  `spare_part_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) DEFAULT NULL,
  `description` varchar(1000) DEFAULT NULL,
  `price` decimal(15,2) DEFAULT NULL,
  `state` varchar(20) NOT NULL,
  `id_item` int DEFAULT NULL,
  `id_repair` int NOT NULL,
  `vendor` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`spare_part_id`),
  KEY `id_item` (`id_item`),
  KEY `id_repair` (`id_repair`),
  CONSTRAINT `spare_part_ibfk_1` FOREIGN KEY (`id_item`) REFERENCES `item` (`item_id`) ON DELETE SET NULL,
  CONSTRAINT `spare_part_ibfk_2` FOREIGN KEY (`id_repair`) REFERENCES `repair` (`repair_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `password` varchar(60) NOT NULL,
  `admin_role` int NOT NULL,
  `image` varchar(100) NOT NULL,
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `warehouse`
--

DROP TABLE IF EXISTS `warehouse`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `warehouse` (
  `warehouse_id` int NOT NULL AUTO_INCREMENT,
  `shelf_number` varchar(10) DEFAULT NULL,
  `compart_number` varchar(10) DEFAULT NULL,
  `box_number` varchar(10) NOT NULL,
  `description` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`warehouse_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-11-09 11:40:08
