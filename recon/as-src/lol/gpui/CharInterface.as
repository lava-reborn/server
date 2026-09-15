class lol.gpui.CharInterface extends lol.gpui.GPUIObject
{
   var ArmorClass;
   var ArmorClassValue;
   var HTTP;
   var _data;
   var attribTitle0;
   var attribTitle1;
   var attribTitle2;
   var attribTitle3;
   var attribTitle4;
   var attribute0;
   var attribute1;
   var attribute2;
   var attribute3;
   var attribute4;
   var charPers_btn;
   var critDodge_txt;
   var crit_txt;
   var currentSpec;
   var dispatchEvent;
   var infoPan;
   var listArr;
   var meleeEvade_title;
   var meleeEvade_value;
   var od_title;
   var od_value;
   var slideList;
   var specArr;
   var specItemArr;
   var xmlArr;
   var xmlInfoLoaded;
   var m = 0;
   function CharInterface()
   {
      super();
      this.doLater("init");
      this.loadDescription();
      lol.core.Master.getInstance().gamer.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.rpUpdate);
   }
   function init()
   {
      lol.core.Master.getInstance().gamer.requestAttributes();
      this.rpUpdate();
      this.infoPan.fillContent();
      this.infoPan.setSize(394,160);
      lol.core.SceneShifter.hotKeyManager.addFilter("persInfo");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER0,this,this.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER1,this,this.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER2,this,this.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER3,this,this.selectFuncKey4);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER4,this,this.selectFuncKey5);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      this.charPers_btn._enabled = false;
      this.charPers_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.gotoCharInterface);
      this.showKrit();
      this.showArmorLevel();
      this.showMeleeEvade();
      this.showOD();
   }
   function showMeleeEvade()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      var _loc3_ = _loc2_.attributes.attrib1.level + _loc2_.attributes.attrib3.level + _loc2_.attributes.skill0.level + _loc2_.attributes.spec1.level;
      if(_loc3_ >= 0)
      {
         this.meleeEvade_value.value.text = _loc3_ + "%";
      }
   }
   function showArmorLevel()
   {
      var _loc4_ = lol.core.Master.getInstance().gamer;
      var _loc5_ = (_loc4_.attributes.attrib1.level * 3 + _loc4_.attributes.attrib3.level) / 4;
      var _loc7_ = _loc4_.equipment.head.item;
      if(_loc7_)
      {
         _loc5_ += _loc7_.getProp("armor_class");
      }
      var _loc11_ = _loc4_.equipment.armor.item;
      if(_loc11_)
      {
         _loc5_ += _loc11_.getProp("armor_class");
      }
      var _loc6_ = _loc4_.equipment.camouflage.item;
      if(_loc6_)
      {
         _loc5_ += _loc6_.getProp("armor_class");
      }
      var _loc9_ = _loc4_.equipment.belt.item;
      if(_loc9_)
      {
         _loc5_ += _loc9_.getProp("armor_class");
      }
      var _loc8_ = _loc4_.equipment.legs.item;
      if(_loc8_)
      {
         _loc5_ += _loc8_.getProp("armor_class");
      }
      var _loc10_ = _loc4_.equipment.boots.item;
      if(_loc10_)
      {
         _loc5_ += _loc10_.getProp("armor_class");
      }
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.effects.getFXArrayLength())
      {
         _loc3_ = _loc4_.effects.getEffect(_loc2_);
         if(_loc3_.armor)
         {
            _loc5_ += _loc3_.armor;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc12_;
      if(_loc5_ >= 0)
      {
         _loc12_ = this.ArmorClassValue;
         _loc12_.value.text = _loc5_;
      }
   }
   function Apply_OD_Bonus(item)
   {
      var _loc1_;
      if(item)
      {
         _loc1_ = item.getProp("bonus_od");
         if(_loc1_ && !isNaN(_loc1_))
         {
            return _loc1_;
         }
      }
      return 0;
   }
   function showOD()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      var _loc5_ = _loc2_.attributes.ap_max;
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.primaryItem);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.secondaryItem);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.head.item);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.armor.item);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.camouflage.item);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.belt.item);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.legs.item);
      _loc5_ += this.Apply_OD_Bonus(_loc2_.equipment.boots.item);
      _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.head.item);
      if(_loc2_.equipment.armor.item.getProp("setTypeID") != _loc2_.equipment.head.item.getProp("setTypeID"))
      {
         _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.armor.item);
      }
      if(_loc2_.equipment.camouflage.item.getProp("setTypeID") != _loc2_.equipment.armor.item.getProp("setTypeID") && _loc2_.equipment.camouflage.item.getProp("setTypeID") != _loc2_.equipment.head.item.getProp("setTypeID"))
      {
         _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.camouflage.item);
      }
      if(_loc2_.equipment.belt.item.getProp("setTypeID") != _loc2_.equipment.camouflage.item.getProp("setTypeID") && _loc2_.equipment.belt.item.getProp("setTypeID") != _loc2_.equipment.armor.item.getProp("setTypeID") && _loc2_.equipment.belt.item.getProp("setTypeID") != _loc2_.equipment.head.item.getProp("setTypeID"))
      {
         _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.belt.item);
      }
      if(_loc2_.equipment.legs.item.getProp("setTypeID") != _loc2_.equipment.camouflage.item.getProp("setTypeID") && _loc2_.equipment.legs.item.getProp("setTypeID") != _loc2_.equipment.armor.item.getProp("setTypeID") && _loc2_.equipment.legs.item.getProp("setTypeID") != _loc2_.equipment.head.item.getProp("setTypeID") && _loc2_.equipment.legs.item.getProp("setTypeID") != _loc2_.equipment.belt.item.getProp("setTypeID"))
      {
         _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.legs.item);
      }
      if(_loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.legs.item.getProp("setTypeID") && _loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.camouflage.item.getProp("setTypeID") && _loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.armor.item.getProp("setTypeID") && _loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.head.item.getProp("setTypeID") && _loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.belt.item.getProp("setTypeID") && _loc2_.equipment.boots.item.getProp("setTypeID") != _loc2_.equipment.legs.item.getProp("setTypeID"))
      {
         _loc5_ += this.getBonusFromSet("_od",_loc2_.equipment.boots.item);
      }
      var _loc4_ = 0;
      var _loc3_;
      while(_loc4_ < _loc2_.effects.getFXArrayLength())
      {
         _loc3_ = _loc2_.effects.getEffect(_loc4_);
         if(_loc3_ && _loc3_.max_od)
         {
            _loc5_ += _loc3_.max_od;
         }
         _loc4_ = _loc4_ + 1;
      }
      if(_loc5_ >= 0)
      {
         this.od_value.value.text = _loc5_;
      }
   }
   function showKrit()
   {
      var _loc3_ = lol.core.Master.getInstance().gamer;
      var _loc17_ = _loc3_.equipment.primaryItem;
      var _loc16_ = _loc17_.getProp("weapon_type");
      _loc17_.removeEventListener("itemUpdate",this,this.showKrit);
      var _loc15_ = _loc3_.attributes.attrib1.level;
      var _loc13_ = _loc3_.attributes.attrib3.level;
      var _loc25_ = _loc3_.attributes.attrib0.level;
      var _loc14_ = _loc3_.attributes.skill1.level;
      var _loc6_;
      var _loc5_;
      var _loc24_;
      if(_loc16_ == lol.core.objects.FireArm.PISTOL)
      {
         _loc24_ = _loc3_.attributes.spec2.level;
         _loc6_ = (_loc15_ * 8 + _loc13_ * 4) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      else if(_loc16_ == lol.core.objects.FireArm.SHOTGUN)
      {
         _loc24_ = _loc3_.attributes.spec3.level;
         _loc6_ = (_loc25_ * 6 + _loc13_ * 6) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      else if(_loc16_ == lol.core.objects.FireArm.ASSAULT)
      {
         _loc24_ = _loc3_.attributes.spec4.level;
         _loc6_ = (_loc15_ * 6 + _loc13_ * 6) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      else if(_loc16_ == lol.core.objects.FireArm.RIFLE)
      {
         _loc24_ = _loc3_.attributes.spec5.level;
         _loc6_ = (_loc15_ * 6 + _loc13_ * 6) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      else if(_loc16_ == lol.core.objects.FireArm.MACHINEGUN)
      {
         _loc24_ = _loc3_.attributes.spec6.level;
         _loc6_ = (_loc25_ * 8 + _loc13_ * 4) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      else if(_loc16_ == lol.core.objects.FireArm.SMG)
      {
         _loc24_ = _loc3_.attributes.spec7.level;
         _loc6_ = (_loc15_ * 6 + _loc13_ * 4) / 4 + _loc14_ / 4 + _loc24_;
         _loc5_ = (_loc15_ + _loc13_) / 2 + _loc14_ / 2 + _loc24_;
      }
      var _loc22_ = _loc3_.equipment.primaryItem;
      var _loc21_;
      var _loc18_;
      if(_loc22_)
      {
         _loc21_ = _loc22_.getProp("bonus_cp");
         if(_loc21_ && !isNaN(_loc21_))
         {
            _loc6_ += _loc21_;
         }
         _loc18_ = _loc22_.getProp("bonus_ce");
         if(_loc18_ && !isNaN(_loc18_))
         {
            _loc5_ += _loc18_;
         }
      }
      var _loc19_ = _loc3_.equipment.secondaryItem;
      var _loc23_;
      var _loc20_;
      if(_loc19_)
      {
         _loc23_ = _loc19_.getProp("bonus_cp");
         if(_loc23_ && !isNaN(_loc23_))
         {
            _loc6_ += _loc23_;
         }
         _loc20_ = _loc19_.getProp("bonus_ce");
         if(_loc20_ && !isNaN(_loc20_))
         {
            _loc5_ += _loc20_;
         }
      }
      var _loc26_;
      var _loc9_ = _loc3_.equipment.head.item;
      if(_loc9_)
      {
         if(_loc9_.getProp("bonus_cp") && !isNaN(_loc9_.getProp("bonus_cp")))
         {
            _loc6_ += _loc9_.getProp("bonus_cp");
         }
         if(_loc9_.getProp("bonus_ce") && !isNaN(_loc9_.getProp("bonus_ce")))
         {
            _loc5_ += _loc9_.getProp("bonus_ce");
         }
      }
      var _loc11_ = _loc3_.equipment.armor.item;
      if(_loc11_)
      {
         if(_loc11_.getProp("bonus_cp") && !isNaN(_loc11_.getProp("bonus_cp")))
         {
            _loc6_ += _loc11_.getProp("bonus_cp");
         }
         if(_loc11_.getProp("bonus_ce") && !isNaN(_loc11_.getProp("bonus_ce")))
         {
            _loc5_ += _loc11_.getProp("bonus_ce");
         }
      }
      var _loc8_ = _loc3_.equipment.camouflage.item;
      if(_loc8_)
      {
         if(_loc8_.getProp("bonus_cp") && !isNaN(_loc8_.getProp("bonus_cp")))
         {
            _loc6_ += _loc8_.getProp("bonus_cp");
         }
         if(_loc8_.getProp("bonus_ce") && !isNaN(_loc8_.getProp("bonus_ce")))
         {
            _loc5_ += _loc8_.getProp("bonus_ce");
         }
      }
      var _loc12_ = _loc3_.equipment.belt.item;
      if(_loc12_)
      {
         if(_loc12_.getProp("bonus_cp") && !isNaN(_loc12_.getProp("bonus_cp")))
         {
            _loc6_ += _loc12_.getProp("bonus_cp");
         }
         if(_loc12_.getProp("bonus_ce") && !isNaN(_loc12_.getProp("bonus_ce")))
         {
            _loc5_ += _loc12_.getProp("bonus_ce");
         }
      }
      var _loc7_ = _loc3_.equipment.legs.item;
      if(_loc7_)
      {
         if(_loc7_.getProp("bonus_cp") && !isNaN(_loc7_.getProp("bonus_cp")))
         {
            _loc6_ += _loc7_.getProp("bonus_cp");
         }
         if(_loc7_.getProp("bonus_ce") && !isNaN(_loc7_.getProp("bonus_ce")))
         {
            _loc5_ += _loc7_.getProp("bonus_ce");
         }
      }
      var _loc10_ = _loc3_.equipment.boots.item;
      if(_loc10_)
      {
         if(_loc10_.getProp("bonus_cp") && !isNaN(_loc10_.getProp("bonus_cp")))
         {
            _loc6_ += _loc10_.getProp("bonus_cp");
         }
         if(_loc10_.getProp("bonus_ce") && !isNaN(_loc10_.getProp("bonus_ce")))
         {
            _loc5_ += _loc10_.getProp("bonus_ce");
         }
      }
      _loc6_ += this.getBonusFromSet("_cp",_loc9_);
      _loc5_ += this.getBonusFromSet("_ce",_loc9_);
      if(_loc11_.getProp("setTypeID") != _loc9_.getProp("setTypeID"))
      {
         _loc6_ += this.getBonusFromSet("_cp",_loc11_);
         _loc5_ += this.getBonusFromSet("_ce",_loc11_);
      }
      if(_loc8_.getProp("setTypeID") != _loc11_.getProp("setTypeID") && _loc8_.getProp("setTypeID") != _loc9_.getProp("setTypeID"))
      {
         _loc6_ += this.getBonusFromSet("_cp",_loc8_);
         _loc5_ += this.getBonusFromSet("_ce",_loc8_);
      }
      if(_loc12_.getProp("setTypeID") != _loc8_.getProp("setTypeID") && _loc12_.getProp("setTypeID") != _loc11_.getProp("setTypeID") && _loc12_.getProp("setTypeID") != _loc9_.getProp("setTypeID"))
      {
         _loc6_ += this.getBonusFromSet("_cp",_loc7_);
         _loc5_ += this.getBonusFromSet("_ce",_loc7_);
      }
      if(_loc7_.getProp("setTypeID") != _loc8_.getProp("setTypeID") && _loc7_.getProp("setTypeID") != _loc11_.getProp("setTypeID") && _loc7_.getProp("setTypeID") != _loc9_.getProp("setTypeID") && _loc7_.getProp("setTypeID") != _loc12_.getProp("setTypeID"))
      {
         _loc6_ += this.getBonusFromSet("_cp",_loc7_);
         _loc5_ += this.getBonusFromSet("_ce",_loc7_);
      }
      if(_loc10_.getProp("setTypeID") != _loc7_.getProp("setTypeID") && _loc10_.getProp("setTypeID") != _loc8_.getProp("setTypeID") && _loc10_.getProp("setTypeID") != _loc11_.getProp("setTypeID") && _loc10_.getProp("setTypeID") != _loc9_.getProp("setTypeID") && _loc10_.getProp("setTypeID") != _loc12_.getProp("setTypeID"))
      {
         _loc6_ += this.getBonusFromSet("_cp",_loc10_);
         _loc5_ += this.getBonusFromSet("_ce",_loc10_);
      }
      var _loc4_ = 0;
      var _loc2_;
      while(_loc4_ < _loc3_.effects.getFXArrayLength())
      {
         _loc2_ = _loc3_.effects.getEffect(_loc4_);
         if(_loc2_)
         {
            if(_loc2_.critical_probability)
            {
               _loc6_ += _loc2_.critical_probability;
            }
            if(_loc2_.critical_evade)
            {
               _loc5_ += _loc2_.critical_probability;
            }
         }
         _loc4_ = _loc4_ + 1;
      }
      if(_loc17_ && _loc17_ instanceof lol.core.objects.FireArm)
      {
         if(isNaN(_loc6_) || isNaN(_loc5_))
         {
            _loc17_.addEventListener("itemUpdate",this,this.showKrit);
         }
         else
         {
            this.crit_txt.text = _loc6_ + " %";
            this.critDodge_txt.text = _loc5_ + " %";
         }
      }
   }
   function getBonusFromSet(bonusName, item)
   {
      var _loc3_ = 0;
      var _loc7_ = item.getProp("setTypeID");
      var _loc5_ = lol.core.sets.SetManager.getSet(_loc7_);
      var _loc4_ = lol.core.Master.getInstance().gamer.equipment.getNumOfSetItem(_loc7_);
      var _loc1_ = 2;
      var _loc2_;
      while(_loc1_ < 7)
      {
         if(_loc4_ >= _loc1_)
         {
            _loc2_ = _loc5_.getProp("bonus_" + _loc1_ + bonusName);
            if(_loc2_)
            {
               _loc3_ += _loc2_;
            }
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc3_;
   }
   function gotoCharInterface()
   {
      var _loc2_ = lol.core.SceneShifter._sl.getWindow("questInfoInterface").content;
      _loc2_.questList_btn._enabled = true;
      this.charPers_btn._enabled = false;
      lol.core.SceneShifter.openSlideWindow("charInterface");
   }
   function cancel()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function close()
   {
      var _loc1_ = new Object();
      _loc1_.data = "char";
      lol.core.SceneShifter._ref.currentScene.openCloseSlideWindow(_loc1_);
   }
   function kill()
   {
      this.killStats();
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.CURRENT_SCILL_CHAR,this.slideList.currentNum);
      lol.core.Master.getInstance().gamer.attributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.rpUpdate);
      lol.core.SceneShifter.hotKeyManager.removeFilter("persInfo");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER0,this,this.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER1,this,this.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER2,this,this.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER3,this,this.selectFuncKey4);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER4,this,this.selectFuncKey5);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      this.charPers_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.gotoCharInterface);
      this.slideList.removeEventListener("MouseMove",this,this.SkillMove);
   }
   function selectFuncKey1()
   {
      this.slideList.open(0);
   }
   function selectFuncKey2()
   {
      this.slideList.open(1);
   }
   function selectFuncKey3()
   {
      this.slideList.open(2);
   }
   function selectFuncKey4()
   {
      this.slideList.open(3);
   }
   function selectFuncKey5()
   {
      this.slideList.open(4);
   }
   function initStats()
   {
      this.attribTitle0.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:0});
      };
      this.attribTitle0.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle1.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:1});
      };
      this.attribTitle1.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle2.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:2});
      };
      this.attribTitle2.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle3.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:3});
      };
      this.attribTitle3.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle4.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:4});
      };
      this.attribTitle4.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute0.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:0});
      };
      this.attribute0.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute1.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:1});
      };
      this.attribute1.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute2.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:2});
      };
      this.attribute2.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute3.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:3});
      };
      this.attribute3.addEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute4.onRollOver = function()
      {
         this.dispatchEvent({type:"onAttribMove",id:4});
      };
      this.attribute4.addEventListener("onAttribMove",this,this.onAttribMove);
      this.ArmorClassValue.onRollOver = function()
      {
         this.dispatchEvent({type:"onACMove"});
      };
      this.ArmorClassValue.addEventListener("onACMove",this,this.onACMove);
      this.ArmorClass.onRollOver = function()
      {
         this.dispatchEvent({type:"onACMove"});
      };
      this.ArmorClass.addEventListener("onACMove",this,this.onACMove);
      this.od_value.onRollOver = function()
      {
         this.dispatchEvent({type:"onOD_Move"});
      };
      this.od_value.addEventListener("onOD_Move",this,this.onOD_Move);
      this.od_title.onRollOver = function()
      {
         this.dispatchEvent({type:"onOD_Move"});
      };
      this.od_title.addEventListener("onOD_Move",this,this.onOD_Move);
      this.meleeEvade_title.onRollOver = function()
      {
         this.dispatchEvent({type:"onME_Move"});
      };
      this.meleeEvade_title.addEventListener("onME_Move",this,this.onME_Move);
      this.meleeEvade_value.onRollOver = function()
      {
         this.dispatchEvent({type:"onME_Move"});
      };
      this.meleeEvade_value.addEventListener("onME_Move",this,this.onME_Move);
   }
   function killStats()
   {
      this.attribTitle0.onRollOver = null;
      this.attribTitle0.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle1.onRollOver = null;
      this.attribTitle1.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle2.onRollOver = null;
      this.attribTitle2.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle3.onRollOver = null;
      this.attribTitle3.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribTitle4.onRollOver = null;
      this.attribTitle4.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute0.onRollOver = null;
      this.attribute0.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute1.onRollOver = null;
      this.attribute1.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute2.onRollOver = null;
      this.attribute2.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute3.onRollOver = null;
      this.attribute3.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.attribute4.onRollOver = null;
      this.attribute4.removeEventListener("onAttribMove",this,this.onAttribMove);
      this.ArmorClassValue.onRollOver = null;
      this.ArmorClassValue.removeEventListener("onACMove",this,this.onACMove);
      this.ArmorClass.onRollOver = null;
      this.ArmorClass.removeEventListener("onACMove",this,this.onACMove);
      this.od_value.onRollOver = null;
      this.od_value.removeEventListener("onOD_Move",this,this.onOD_Move);
      this.od_title.onRollOver = null;
      this.od_title.removeEventListener("onOD_Move",this,this.onOD_Move);
      this.meleeEvade_title.onRollOver = null;
      this.meleeEvade_title.addEventListener("onME_Move",this,this.onME_Move);
      this.meleeEvade_value.onRollOver = null;
      this.meleeEvade_value.addEventListener("onME_Move",this,this.onME_Move);
   }
   function rpUpdate(obj)
   {
      this.slideList.setSize(410,180);
      this.initArray();
      this.slideList.erase();
      this.listArr = this.slideList.build(this.specArr);
      this.slideList.addEventListener("MouseMove",this,this.SkillMove);
      this.attachSpec();
      this.doLater("initStats");
      var _loc8_ = lol.core.Master.getInstance().gamer.attributes;
      var _loc5_ = _loc8_.attribArray;
      var _loc6_ = _loc5_.length;
      var _loc9_ = new TextFormat();
      _loc9_.bold = true;
      var _loc2_ = 0;
      var _loc7_;
      var _loc4_;
      var _loc3_;
      while(_loc2_ < _loc6_)
      {
         _loc4_ = _loc5_[_loc2_].bonus;
         _loc3_ = this["attribute" + _loc2_];
         _loc3_.value.text = _loc5_[_loc2_].value + _loc4_;
         _loc2_ = _loc2_ + 1;
      }
      this.doLater("openSharedNum");
   }
   function SkillMove(obj)
   {
      var _loc2_;
      if(obj && obj.data != undefined)
      {
         _loc2_ = obj.data._parent.num;
         this.showSkillDesc(_loc2_);
      }
   }
   function openSharedNum()
   {
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CURRENT_SCILL_CHAR);
      if(_loc2_ != undefined)
      {
         this.slideList.open(_loc2_);
      }
   }
   function initArray()
   {
      var _loc6_ = lol.core.Master.getInstance().gamer.attributes;
      var _loc3_ = _loc6_.skillArray;
      var _loc11_ = _loc6_.specArray;
      this.specArr = new Array();
      var _loc2_ = 0;
      while(_loc2_ < 4)
      {
         this.specArr[_loc2_] = {title:_loc3_[_loc2_].title,linkTitle:"slide" + _loc2_ + "_btn",linkContent:"contextListPan",skillNum:_loc3_[_loc2_].levelString,currentSkill:_loc3_[_loc2_].currentValue,spec:_loc3_[_loc2_].specArr};
         _loc2_ = _loc2_ + 1;
      }
      var _loc5_ = lol.core.Master.getInstance().gamer.reputations;
      var _loc4_;
      if(_loc5_)
      {
         _loc4_ = _loc5_._reputations;
         if(_loc4_)
         {
            this.specArr[4] = {title:"Навык бойца",linkTitle:"pvp_skill_slide",linkContent:"contextListPan",skillNum:_loc4_[0].levelString,currentSkill:_loc4_[0].currentValue,spec:_loc4_[0].frac_rep_Arr,nextLevel:_loc4_[0].nextLevel(),estimateRep:_loc4_[0].estimateReputation()};
         }
         else
         {
            trace("REP.CharInterface.initArray => repArray = undefined");
         }
      }
      else
      {
         trace("REP.CharInterface.initArray => reputations = undefined");
      }
   }
   function loadDescription()
   {
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      var _loc2_ = lol.services.SSEmulator.getSpecXmlURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      this.xmlInfoLoaded = true;
      this.parse(obj.data);
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
   }
   function parse(doc)
   {
      this.xmlArr = new Array();
      var _loc5_ = doc.firstChild.childNodes;
      var _loc3_;
      var _loc4_;
      var _loc2_;
      for(var _loc7_ in _loc5_)
      {
         _loc3_ = new Object();
         _loc3_ = _loc5_[_loc7_].attributes;
         _loc4_ = new Array();
         _loc2_ = _loc5_[_loc7_].childNodes;
         for(var _loc6_ in _loc2_)
         {
            _loc4_.push(_loc2_[_loc6_].childNodes[0]);
         }
         _loc3_.arr = _loc4_;
         this.xmlArr["s" + _loc5_[_loc7_].attributes.id] = _loc3_;
      }
   }
   function attachSpec()
   {
      var _loc9_ = 0;
      var _loc5_ = 0;
      var _loc4_;
      var _loc3_;
      var _loc8_;
      var _loc2_;
      var _loc6_;
      var _loc15_;
      var _loc7_;
      var _loc13_;
      var _loc12_;
      var _loc14_;
      while(_loc5_ < this.listArr.length)
      {
         _loc4_ = this.listArr[_loc5_].listBtn.cont;
         _loc3_ = this.specArr[_loc5_].spec;
         _loc4_.setSize(400,177);
         _loc4_.lineSpace = -6;
         _loc4_.typeOfAlign = 0;
         _loc8_ = true;
         _loc2_ = 0;
         while(_loc2_ < _loc3_.length)
         {
            if(_loc3_[_loc2_].currentValue != undefined)
            {
               _loc6_ = _loc3_[_loc2_];
               _loc8_ = false;
               _loc4_.listItemLink = "slideItem";
               _loc15_ = _loc4_.addItem({label:_loc3_[_loc2_].title + ", " + _loc3_[_loc2_].level,data:_loc3_[_loc2_]});
               _loc15_.addEventListener("onMove",this,this.onMoveSpec);
               _loc15_.onRollOver = function()
               {
                  this.dispatchEvent({type:"onMove",data:this._data});
               };
               _loc7_ = _loc6_.xp_specs + " из " + _loc6_.xp_max_specs;
               this.doLater("initHint",[lol.gpui.HintManager["BG" + _loc9_],_loc15_.bg,_loc7_]);
               this.specItemArr.push(_loc15_);
            }
            _loc9_ = _loc9_ + 1;
            _loc2_ = _loc2_ + 1;
         }
         if(_loc8_)
         {
            if(this.specArr[_loc5_].linkTitle != "pvp_skill_slide")
            {
               _loc4_.listItemLink = "noSpec";
               _loc15_ = _loc4_.addItem({label:"Нет изучаемых специализаций"});
            }
            else
            {
               _loc4_.listItemLink = "noSpec";
               _loc13_ = this.specArr[_loc5_].estimateRep;
               _loc12_ = this.specArr[_loc5_].nextLevel;
               _loc14_ = "Осталось " + _loc13_ + " очков до звания \"" + _loc12_ + "\"";
               _loc15_ = _loc4_.addItem({label:_loc14_});
            }
         }
         _loc5_ = _loc5_ + 1;
      }
   }
   function onMoveSpec(obj)
   {
      if(obj.data)
      {
         this.showDesc(this.xmlArr["s" + obj.data.id],obj.data);
      }
   }
   function initHint(inst, mov, hint)
   {
      lol.core.SceneShifter.hintManager.addHint(inst,mov,hint);
   }
   function selectSpec(obj)
   {
      var _loc2_;
      if(this.currentSpec != obj.target)
      {
         this.currentSpec.toggled = false;
         this.currentSpec = obj.target;
         _loc2_ = this.xmlArr["s" + obj.target.data.id];
      }
      else
      {
         this.currentSpec = null;
         _loc2_ = "none";
      }
      this.showDesc(_loc2_,obj.target.data);
   }
   function showInfo()
   {
      var _loc2_;
      if(this.m == 0)
      {
         this.m = 1;
         _loc2_ = this.slideList.container.slide0_btn.cont.cont_mc;
      }
   }
   function onME_Move(obj)
   {
      this.showAbstractDesc("Вероятность избежать попадания холодным оружием.");
   }
   function onOD_Move(obj)
   {
      this.showAbstractDesc("Количество очков действия значительно увеличивает эффективность вашего персонажа в бою.<br><br>Параметр увеличивается вместе с максимально прокачанным навыком.");
   }
   function onACMove(obj)
   {
      this.showAbstractDesc("Класс брони определяет количество повреждений, которые будут перенаправлены на выносливость и не нанесут вреда вашим очкам жизни.<br>Параметр зависит от ловкости и восприятия");
   }
   function onAttribMove(obj)
   {
      this.showAttribDesc(obj.id);
   }
   function showAttribDesc(attrNum)
   {
      var _loc2_;
      switch(attrNum)
      {
         case 0:
            _loc2_ = "Параметр увеличивает:<ul><li>Повреждения в рукопашном бою и холодным оружием</li><li>Переносимый вес</li><li>Количество очков здоровья персонажа</li><li>Вероятность критического попадания из дробовиков и пулеметов</li></ul>Параметр прокачивается специализациями:<ul><li>Рукопашный бой</li><li>Дробовики</li><li>Ручные пулеметы</li></ul>";
            break;
         case 1:
            _loc2_ = "Параметр увеличивает:<ul><li>Вероятность уклонения от атаки в ближнем бою;</li><li>Вероятность критического попадания и избежания критического попадания в ближнем бою, из пистолетов, ПП, автоматом и винтовок;</li><li>Значение брони персонажа и количество очков выносливости.</li></ul>Параметр прокачивается специализациями:<ul><li>Режущее оружие</li><li>Автоматы</li><li>Пистолет-пулемет</li><li>Первая помощь</li></ul>";
            break;
         case 2:
            _loc2_ = "Параметр увеличивает:<ul><li>Количество очков жизни персонажа</li><li>Количество выносливости персонажа</li><li>Регенерацию очков жизни и выносливости.</li></ul>Параметр прокачивается с максимально прокачанным навыком.";
            break;
         case 3:
            _loc2_ = "Параметр увеличивает:<ul><li>Значение брони персонажа;</li><li>Вероятность уклонения от атаки в ближнем бою;</li><li>Вероятность критического попадания из всех видов огнестрельного оружия;</li><li>Вероятность избежать критического попадания в ближнем бою и из огнестрельного оружия.</li></ul>Параметр прокачивается специализациями:<ul><li>Пистолеты</li><li>Винтовки</li></ul>";
            break;
         case 4:
            _loc2_ = "Параметр увеличивает:<ul><li>Урон из всех видов огнестрельного оружия.</li></ul>Параметр прокачивается специализациями:<ul><li>Хирургия</li></ul>";
            break;
         default:
            _loc2_ = "none";
      }
      this.showAbstractDesc(_loc2_);
   }
   function showSkillDesc(skillNum)
   {
      var _loc2_;
      switch(skillNum)
      {
         case 0:
            _loc2_ = "Навык увеличивает вероятности:<br><ul><li>Попадания в рукопашном бою и холодным оружием</li><li>Уклониться от атаки в ближнем бою</li><li>Критического попадания в ближнем бою</li><li>Избежать критического попадания в ближнем бою</li></ul>Навык прокачивается при использовании оружия ближнего боя.";
            break;
         case 1:
            _loc2_ = "Навык увеличивает вероятности:<br><ul><li>Попадания из огнестрельного оружия</li><li>Критического попадания из огнестрельного оружия</li><li>Избежать критического попадания из огнестрельного оружия</li></ul>Навык прокачивается при использовании огнестрельного оружия.";
            break;
         case 2:
            _loc2_ = "Навык увеличивает количество HP и выносливости, восстанавливаемых с помощью медицинских препаратов.<br><br>Навык прокачивается при использовании медицинских препаратов.";
            break;
         default:
            _loc2_ = "none";
      }
      this.showAbstractDesc(_loc2_);
   }
   function showAbstractDesc(description)
   {
      this.infoPan.content.removeMovieClip();
      this.infoPan.fillContent();
      var _loc2_ = this.infoPan.content.attachMovie("skillInfo_title_","skillInfo_title_",this.infoPan.content.getNextHighestDepth());
      _loc2_.txt.autoSize = true;
      _loc2_.txt.wordWrap = true;
      var _loc3_;
      if(description != "none")
      {
         _loc3_ = new TextFormat();
         _loc3_.bold = true;
         _loc2_.txt.htmlText = description;
         _loc2_.txt.setTextFormat(_loc3_);
      }
      else
      {
         _loc2_.txt.text = "Для данного элемента нет описания";
      }
   }
   function showDesc(xmlObj, btnObj)
   {
      this.infoPan.content.removeMovieClip();
      this.infoPan.fillContent();
      var _loc5_ = this.infoPan.content.attachMovie("skillInfo_title_","skillInfo_title_",this.infoPan.content.getNextHighestDepth());
      _loc5_.txt.autoSize = true;
      _loc5_.txt.wordWrap = true;
      var _loc7_;
      var _loc4_;
      var _loc2_;
      if(xmlObj)
      {
         if(xmlObj != "none")
         {
            _loc7_ = new TextFormat();
            _loc7_.bold = true;
            _loc5_.txt.text = xmlObj.title;
            _loc5_.txt.setTextFormat(_loc7_);
            _loc4_ = _loc5_._y + _loc5_._height;
            for(var _loc6_ in xmlObj.arr)
            {
               _loc2_ = this.infoPan.content.attachMovie("skillInfo_item_","skillInfo_item_",this.infoPan.content.getNextHighestDepth());
               _loc2_.txt.autoSize = true;
               _loc2_.txt.wordWrap = true;
               _loc2_._y = _loc4_;
               _loc2_.txt.htmlText = xmlObj.arr[_loc6_];
               _loc4_ = _loc2_._y + _loc2_._height;
            }
         }
      }
      else
      {
         _loc5_.txt.text = "У этой специализации нет описания или оно еще не загрузилось.";
      }
   }
}
