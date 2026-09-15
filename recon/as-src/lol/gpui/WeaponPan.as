class lol.gpui.WeaponPan extends lol.gpui.GPUIObject
{
   var BY;
   var TTY;
   var TY;
   var _alpha;
   var _parent;
   var _x;
   var _y;
   var animationTime;
   var attachMovie;
   var closeEQ;
   var curMode_btn;
   var curType;
   var cw_btn;
   var eat_btn;
   var equipment;
   var fireArm_mod_mc;
   var gamer;
   var getNextHighestDepth;
   var healItem;
   var heal_btn;
   var hidePan_btn;
   var icon_mc;
   var item;
   var last_ammo_count;
   var mainSlot;
   var msDamper;
   var onEnterFrame;
   var openEQ;
   var over;
   var reloadAlert;
   var reloadItem;
   var reload_btn;
   var strikeItem;
   var timeBar_mc;
   var timeOfStart;
   var um1_btn;
   var um2_btn;
   var um0_btn;
   var panActivationFlag = false;
   var criticalAmmo = 3;
   var mainSlotRY = 403;
   var mainSlotLY = 153;
   var msDamperRY = 614;
   var msDamperLY = 364;
   var paramAnimation = 2;
   var changeFlag = true;
   var ammo_count = 100;
   var timeStep = 10;
   var curTime = 0;
   var scaleStep = 0;
   var encreaseAlpha = true;
   function WeaponPan()
   {
      super();
      this.timeBar_mc._xscale = 0;
      var _loc3_ = lol.core.Master.getInstance();
      this.gamer = _loc3_.gamer;
      this.equipment = this.gamer.equipment;
      this.equipment.addEventListener("changePrimary",this);
      lol.utils.EMouse.addEventListener(lol.utils.EMouse.DOUBLE_CLICK,this);
      _loc3_.currentLocation.addEventListener("fire",this);
      this.equipment.actionSlotsRequest();
      this.panActivationFlag = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.WEAPON_PAN_OPEN);
      this.mainSlot.slide = function(x)
      {
         this._parent.mcSlide(this,x);
      };
      this.msDamper.slide = function(x)
      {
         this._parent.mcSlide(this,x);
      };
      this.mainSlot.bg_mc.onRollOver = mx.utils.Delegate.create(this,this.weaponOver);
      this.mainSlot.bg_mc.onRollOut = mx.utils.Delegate.create(this,this.weaponOut);
      if(this.panActivationFlag)
      {
         this._parent.weaponMask.gotoAndStop(2);
      }
      this.propeties();
      this.changePrimary();
      this.doLater("init");
   }
   function init()
   {
      this.reloadAlert = this._parent.weapon_bottom.reloadAlert;
      this.cw_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.changeWeapon);
      this.hidePan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.WEAPON_PAN,this,this.openClose);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.HEAL,this,this.heal_func);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.EAT,this,this.eat_func);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CHANGE_WEAPON,this,this.changeWeapon);
      this.um0_btn = this._parent.weapon_bottom.um0_btn;
      this.um1_btn = this._parent.weapon_bottom.um1_btn;
      this.um2_btn = this._parent.weapon_bottom.um2_btn;
      this.reload_btn = this._parent.weapon_bottom.reload_btn;
      this.heal_btn = this._parent.weapon_bottom.heal_btn;
      this.eat_btn = this._parent.weapon_bottom.eat_btn;
      lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.HEAL,this.heal_btn);
      lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.EAT,this.eat_btn);
      this.um0_btn.enabled = false;
      this.um1_btn.enabled = false;
      this.um2_btn.enabled = false;
      this.reload_btn.enabled = false;
      trace("reload_btn1 = false");
      this.um0_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.useMode);
      this.um1_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.useMode);
      this.um2_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.useMode);
      this.heal_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.heal);
      this.eat_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.eat);
      this.heal_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.showHealAP);
      this.eat_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.showHealAP);
      this.heal_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.hideHealAP);
      this.eat_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.hideHealAP);
      this.heal_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.hideHealAP);
      this.eat_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.hideHealAP);
      this.equipment.addEventListener("addItem",this,this.updateHealBtn);
      this.equipment.addEventListener("removeItem",this,this.updateHealBtn);
      this.equipment.addEventListener("updateHealItem",this,this.updateHealBtn);
      this.equipment.addEventListener("updateEatItem",this,this.updateHealBtn);
      this.doLater("updateHealBtn");
      lol.core.Master.getInstance().currentLocation.addEventListener("aim",this,this.aim);
      lol.core.Master.getInstance().currentLocation.addEventListener(lol.events.TimeBarEvent.SHOT,this,this.endTimeBar);
      lol.core.Master.getInstance().currentLocation.addEventListener(lol.events.TimeBarEvent.STRIKE,this,this.endTimeBar);
      lol.core.Master.getInstance().gamer.equipment.addEventListener(lol.events.TimeBarEvent.RELOAD,this,this.reload);
      lol.core.Master.getInstance().gamer.equipment.addEventListener(lol.events.TimeBarEvent.UNLOAD,this,this.unload);
      lol.core.Master.getInstance().gamer.addEventListener(lol.events.TimeBarEvent.HEAL,this,this.healTimeBar);
      lol.core.Master.getInstance().gamer.equipment.addEventListener(lol.events.TimeBarEvent.HEAL,this,this.healTimeBar);
      lol.core.Master.getInstance().gamer.itemActivator.addEventListener(lol.events.TimeBarEvent.STRIKE,this,this.strike);
      lol.core.Master.getInstance().gamer.equipment.addEventListener(lol.events.TimeBarEvent.END_HEAL,this,this.endTimeBar);
      lol.core.Master.getInstance().currentLocation.addEventListener("moveWalker",this,this.breakTimeBar);
   }
   function kill()
   {
      this.openEQ.kill();
      this.closeEQ.kill();
      this.cw_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.changeWeapon);
      this.hidePan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.WEAPON_PAN,this,this.openClose);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CHANGE_WEAPON,this,this.changeWeapon);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.HEAL,this,this.heal_func);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.EAT,this,this.eat_func);
      this.heal_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.heal);
      this.eat_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.eat);
      this.heal_btn.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.showHealAP);
      this.heal_btn.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.hideHealAP);
      this.heal_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.hideHealAP);
      this.equipment.removeEventListener("addItem",this,this.updateHealBtn);
      this.equipment.removeEventListener("removeItem",this,this.updateHealBtn);
      this.equipment.removeEventListener("updateHealItem",this,this.updateHealBtn);
      this.equipment.removeEventListener("updateEatItem",this,this.updateHealBtn);
      lol.core.Master.getInstance().currentLocation.removeEventListener("aim",this,this.aim);
      lol.core.Master.getInstance().currentLocation.removeEventListener(lol.events.TimeBarEvent.SHOT,this,this.endTimeBar);
      lol.core.Master.getInstance().gamer.equipment.removeEventListener(lol.events.TimeBarEvent.RELOAD,this,this.reload);
      lol.core.Master.getInstance().gamer.equipment.removeEventListener(lol.events.TimeBarEvent.HEAL,this,this.healTimeBar);
      lol.core.Master.getInstance().gamer.equipment.removeEventListener(lol.events.TimeBarEvent.END_HEAL,this,this.endTimeBar);
      lol.core.Master.getInstance().gamer.itemActivator.removeEventListener(lol.events.TimeBarEvent.STRIKE,this,this.strike);
      lol.core.Master.getInstance().currentLocation.removeEventListener("moveWalker",this,this.breakTimeBar);
   }
   function openClose()
   {
      this.panActivation();
   }
   function onDoubleClick(obj)
   {
      var _loc2_ = this.equipment.primaryItem;
      var _loc3_ = _loc2_.rootID;
      if(this.over && _loc3_ == lol.core.objects.Item.HEAL_ITEM)
      {
         this.equipment.useToYourSelf(_loc2_);
      }
   }
   function weaponOver()
   {
      this.over = true;
   }
   function weaponOut()
   {
      this.over = false;
   }
   function propeties()
   {
      if(this.panActivationFlag)
      {
         this.TY = this._y;
      }
      else
      {
         this.TY = this._y - 80;
      }
      this.TTY = this.TY - 20;
      this.BY = this.TY + 80;
      this.openEQ = new lol.events.EventQueue();
      this.openEQ.addEvent(this,"slided",[this.TTY],0);
      this.openEQ.addEvent(this._parent.weaponMask,"gotoAndStop",[2],200);
      this.openEQ.addEvent(this,"slided",[this.TY],0);
      this.closeEQ = new lol.events.EventQueue();
      this.closeEQ.addEvent(this,"slided",[this.TTY],0);
      this.closeEQ.addEvent(this._parent.weaponMask,"gotoAndStop",[1],200);
      this.closeEQ.addEvent(this,"slided",[this.BY],0);
   }
   function mcSlide()
   {
      delete this.onEnterFrame;
      this.msDamper.onEnterFrame = function()
      {
         this._x += Math.round((this._parent.msDamperLY - this._x) / this._parent.paramAnimation) * 2;
         if(this._parent.mainSlot._x < this._parent.mainSlotRY)
         {
            this._parent.mainSlot._x += Math.round((this._parent.mainSlotRY - this._parent.mainSlot._x) / this._parent.paramAnimation);
         }
         if(Math.abs(this._parent.msDamperLY - this._x) < 2)
         {
            this._x = this._parent.msDamperLY;
            this._parent.mainSlot._x = this._parent.mainSlotLY;
            delete this.onEnterFrame;
            this._parent.attachIcon(this._parent.equipment.primaryItem);
            this.onEnterFrame = function()
            {
               this._x += Math.round((this._parent.msDamperRY - this._x) / this._parent.paramAnimation) * 2;
               this._parent.mainSlot._x += Math.round((this._parent.mainSlotRY - this._parent.mainSlot._x) / this._parent.paramAnimation) * 2;
               if(Math.abs(this._parent.msDamperRY - this._x) < 2)
               {
                  this._x = this._parent.msDamperRY;
                  this._parent.mainSlot._x = this._parent.mainSlotRY;
                  delete this.onEnterFrame;
                  this._parent.dispatchEvent({type:"finish"});
               }
            };
         }
      };
   }
   function slided(y)
   {
      this.onEnterFrame = function()
      {
         this._y += (y - this._y) / 2;
         if(Math.abs(y - this._y) < 2)
         {
            this._y = y;
            delete this.onEnterFrame;
         }
      };
   }
   function panActivation()
   {
      this.panActivationFlag = !this.panActivationFlag;
      if(this.panActivationFlag)
      {
         this.openEQ.Start();
      }
      else
      {
         this.closeEQ.Start();
      }
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.WEAPON_PAN_OPEN,this.panActivationFlag);
   }
   function changeWeapon()
   {
      if(this.changeFlag)
      {
         this.changeFlag = false;
         this.equipment.changePrimary();
      }
   }
   function changePrimary(obj)
   {
      this.item.removeEventListener("itemUpdate",this);
      var _loc2_ = this.item;
      this.item = this.equipment.primaryItem;
      this.item.addEventListener("itemUpdate",this);
      this.itemUpdate();
      this.mcSlide();
      this.changeFlag = true;
   }
   function showAmount(str)
   {
      this.mainSlot.amount_mc.attachText = "numChar";
      this.mainSlot.amount_mc.alignText = "right";
      this.mainSlot.amount_mc.letterSpace = -3;
      this.mainSlot.amount_mc.showValue(str);
   }
   function reloadAlertFunc(b)
   {
      this.reloadAlert = this._parent.weapon_bottom.reloadAlert;
      if(b)
      {
         lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.RELOAD,this.reload_btn,"Оружие не заряжено. Нажмите кнопку перезарядки",false);
         lol.core.SceneShifter._ref.currentScene.weapon_bottom.reload_btn.showHint();
      }
      else
      {
         lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.RELOAD,this.reload_btn,"Перезарядка",true);
      }
      if(b && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRITICAL_AMMO_ALARM))
      {
         var k = true;
         var count = 0;
         this.reloadAlert.onEnterFrame = function()
         {
            if(k)
            {
               if(count < 100)
               {
                  count += 10;
               }
               else
               {
                  count = 100;
                  this._alpha = 100;
                  k = false;
               }
            }
            else if(count > 0)
            {
               count -= 10;
            }
            else
            {
               count = 0;
               this._alpha = 0;
               k = true;
            }
         };
      }
      else
      {
         delete this.reloadAlert.onEnterFrame;
         this.reloadAlert._alpha = 0;
      }
   }
   function itemUpdate(obj)
   {
      var _loc3_ = lol.core.Master.getInstance();
      this.gamer = _loc3_.gamer;
      this.equipment = this.gamer.equipment;
      this.showAmount("");
      var _loc10_ = this.item.getProp("name");
      this.mainSlot.name_txt.text = _loc10_.toUpperCase();
      var _loc2_ = this.item.rootID;
      this.reload_btn.enabled = false;
      trace("reload_btn3 = false");
      var _loc12_;
      var _loc4_;
      var _loc11_;
      var _loc7_;
      var _loc9_;
      var _loc6_;
      if(_loc2_ == lol.core.objects.Item.FIRE_ARM)
      {
         this.reload_btn.enabled = true;
         this.last_ammo_count = this.ammo_count;
         this.ammo_count = this.item.getProp("ammo_count") == undefined ? "" : this.item.getProp("ammo_count");
         _loc12_ = this.item.getProp("clip_size") == undefined ? "" : this.item.getProp("clip_size");
         this.doLater("updateAmmoNumber");
         this.flareWeapon();
         this.showBreak(this.item);
         _loc4_ = this.item.getProp("cur_mode");
         _loc11_ = new lol.utils.Timeout(this,this.showUseMode,500,_loc4_);
      }
      else if(_loc2_ == lol.core.objects.Item.HEAL_ITEM)
      {
         _loc7_ = this.item.getProp("use_count");
         _loc9_ = this.item.getProp("max_use_count");
         _loc6_ = _loc7_ + "/" + _loc9_;
         this.doLater("showAmount",[_loc6_]);
         this.reloadAlertFunc(false);
         this.reloadAlert._alpha = 0;
      }
      else if(_loc2_ == lol.core.objects.Item.COLD_ARM)
      {
         this.showBreak(this.item);
         this.reloadAlertFunc(false);
         this.reloadAlert._alpha = 0;
      }
      var _loc5_;
      if(this.item instanceof lol.core.objects.FireArm)
      {
         _loc5_ = lol.core.objects.FireArm(this.item);
         if(_loc5_.ammoCount == 0)
         {
            lol.services.GameEvents.addEvent(lol.services.GameEvents.UNLOAD_FIREARM,{itemname:this.item});
         }
      }
      var _loc8_;
      if(this.item instanceof lol.core.objects.Breakable)
      {
         _loc8_ = lol.core.objects.Breakable(this.item);
         if(_loc8_.getCurQuality() == 0)
         {
            lol.services.GameEvents.addEvent(lol.services.GameEvents.BREAK,{itemname:this.item});
         }
      }
   }
   function reloadloadFireArm()
   {
      this.equipment.loadPrimary();
   }
   function attachIcon(item)
   {
      this.icon_mc.removeMovieClip();
      this.mainSlot.name_txt.text = "";
      this.mainSlot.modeType_txt.text = "";
      this.showBreakAlert(false);
      this.mainSlot.breakBar._visible = false;
      var _loc3_;
      var _loc5_;
      var _loc4_;
      var _loc6_;
      if(item && item.oID)
      {
         this.icon_mc = lol.display.DisplaySprite.create(this.mainSlot.weapSlot,"icon_mc",0);
         if(item.rootID == lol.core.objects.Item.FIRE_ARM)
         {
            this.reload_btn.enabled = true;
         }
         else
         {
            this.reload_btn.enabled = false;
            trace("reload_btn2 = false");
            this.um0_btn.enabled = false;
            this.um1_btn.enabled = false;
            this.um2_btn.enabled = false;
            this.um0_btn.toggled = false;
            this.um1_btn.toggled = false;
            this.um2_btn.toggled = false;
         }
         if(item.rootID == lol.core.objects.Item.FIRE_ARM || item.rootID == lol.core.objects.Item.WEAR || item.rootID == lol.core.objects.Item.COLD_ARM)
         {
            this.mainSlot.name_txt._y = 54;
            this.mainSlot.breakBar._visible = true;
            this.doLater("showBreak",[item]);
         }
         else
         {
            this.mainSlot.name_txt._y = 56;
            this.showBreakAlert(false);
         }
         _loc3_ = item.typeID;
         _loc5_ = lol.services.SSEmulator.getIcon(_loc3_);
         this.icon_mc.display(_loc3_ + "_icon",_loc5_);
         this.attachBack(Number(item.rootID));
         _loc4_ = !item.getProp("sub_name") ? "" : item.getProp("sub_name");
         this.mainSlot.modeType_txt.text = _loc4_.toUpperCase();
         if(item.inited)
         {
            _loc6_ = item.getProp("name");
            this.mainSlot.name_txt.text = _loc6_.toUpperCase();
         }
         else
         {
            this.mainSlot.name_txt.text = item.id;
            item.addEventListener("itemUpdate",this);
         }
      }
      else
      {
         this.attachBack();
         this.reloadAlertFunc(false);
      }
   }
   function attachAmmoMode()
   {
      this.fireArm_mod_mc.removeMovieClip();
      this.fireArm_mod_mc = this.attachMovie("fireArm_mod_mc","mod_mc",this.getNextHighestDepth());
      this.fireArm_mod_mc._x = 139;
      this.fireArm_mod_mc._y = 52;
      this.mainSlot.amount_mc._x = 135;
      var _loc9_ = this.equipment.primaryItem;
      var _loc6_ = lol.core.Master.getInstance().gamer.equipment.getAmmo(_loc9_);
      var _loc8_ = _loc9_.getProp("ammoType");
      var _loc3_;
      var _loc2_;
      var _loc7_;
      var _loc4_;
      var _loc5_;
      if(_loc8_)
      {
         _loc3_ = 0;
         while(_loc3_ < _loc6_.length)
         {
            _loc2_ = _loc6_[_loc3_];
            _loc2_.removeEventListener("itemUpdate",this,this.attachAmmoMode);
            if(_loc2_.inited)
            {
               _loc7_ = _loc2_.getProp("mod_type");
               if(_loc2_.typeID == _loc8_)
               {
                  _loc4_ = _loc2_.getProp("mod_type");
                  _loc5_ = lol.core.objects.Ammo.MOD_ARR[_loc4_];
                  this.fireArm_mod_mc.gotoAndStop(_loc5_);
               }
            }
            else
            {
               _loc2_.addEventListener("itemUpdate",this,this.attachAmmoMode);
            }
            _loc3_ = _loc3_ + 1;
         }
      }
      else
      {
         this.fireArm_mod_mc.gotoAndStop(8);
      }
   }
   function attachBack(bID)
   {
      var _loc2_;
      switch(bID)
      {
         case lol.core.objects.Item.HEAL_ITEM:
            _loc2_ = "medikKitBG_big";
            break;
         case lol.core.objects.Item.FIRE_ARM:
            _loc2_ = "fireArmBG_big";
            break;
         case lol.core.objects.Item.COLD_ARM:
            _loc2_ = "fireArmBG_big";
            break;
         default:
            _loc2_ = "noneBG_big";
      }
      var _loc3_ = this.mainSlot.bg_mc.attachMovie(_loc2_,"bg",1);
   }
   function showBreak(item)
   {
      var _loc4_ = item.getProp("__break");
      var _loc3_ = item.getProp("max_break_cur");
      var _loc6_ = Math.round(_loc4_ * 100 / _loc3_);
      var _loc7_ = 101 - _loc6_;
      this.mainSlot.breakBar.bar_mc.gotoAndStop(_loc7_);
      var _loc5_ = item.getProp("max_break_abs");
      var _loc2_ = Math.round(_loc3_ * 100 / _loc5_);
      _loc2_ = _loc2_ > 100 ? 100 : _loc2_;
      this.mainSlot.breakBar.bar_mc._xscale = _loc2_;
      if(_loc4_ == 0)
      {
         this.showBreakAlert(true);
      }
      else
      {
         this.showBreakAlert(false);
      }
   }
   function showBreakAlert(b)
   {
      this.mainSlot.breakBar.bar_mc.alert_mc._visible = b;
      if(b)
      {
         this.mainSlot.breakBar.alert_mc.play();
      }
      else
      {
         this.mainSlot.breakBar.alert_mc.gotoAndStop(1);
      }
   }
   function flareWeapon()
   {
      var _loc3_ = this.item.getProp("clip_size");
      this.criticalAmmo = Math.floor(_loc3_ * lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_CRITICAL_AMMO) / 100);
      if(this.criticalAmmo == 0 && _loc3_ > 1)
      {
         this.criticalAmmo = 1;
      }
      var _loc2_;
      var _loc4_;
      if(this.ammo_count == 0)
      {
         this.reloadAlertFunc(true);
         _loc2_ = lol.core.SceneShifter.openNewAlert("topSimple");
         if(this.checkAvailableAmmo(this.item))
         {
            _loc2_.label = "Требуется перезарядка";
         }
         else
         {
            _loc2_.label = "Кончились патроны";
         }
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
      else if(this.ammo_count <= this.criticalAmmo && this.ammo_count != undefined)
      {
         this.reloadAlertFunc(false);
         this.reloadAlert._alpha = 100;
      }
      else
      {
         this.reloadAlertFunc(false);
         this.reloadAlert._alpha = 0;
      }
   }
   function checkAvailableAmmo(fireArm)
   {
      var _loc5_ = this.equipment.bag.getItems();
      var _loc3_ = 0;
      var _loc2_;
      while(_loc3_ < _loc5_.length)
      {
         _loc2_ = _loc5_[_loc3_];
         if(_loc2_ instanceof lol.core.objects.Ammo)
         {
            if(fireArm.compare(_loc2_))
            {
               if(fireArm.ammoCount == 0 || _loc2_.typeID == fireArm.ammoType)
               {
                  return true;
               }
            }
         }
         _loc3_ = _loc3_ + 1;
      }
      return false;
   }
   function fire(obj)
   {
      var _loc1_;
      var _loc2_;
      if(obj.access == false)
      {
         if(obj.res == 43)
         {
            _loc1_ = lol.core.SceneShifter.openNewAlert("topSimple");
            _loc1_.label = "У вас не хватает репутации для использования предмета";
            _loc2_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
         }
      }
   }
   function heal()
   {
      var _loc4_ = this.gamer.attributes.health;
      var _loc2_ = this.gamer.attributes.maxHealth;
      var _loc3_;
      var _loc5_;
      if(_loc4_ >= _loc2_)
      {
         _loc3_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc3_.label = "Вы уже полностью здоровы";
         _loc5_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
      else
      {
         this.equipment.useHealItem();
      }
   }
   function eat()
   {
      var _loc3_ = this.gamer.attributes.stamina;
      var _loc4_ = this.gamer.attributes.maxStamina;
      var _loc2_;
      var _loc5_;
      if(_loc3_ >= _loc4_)
      {
         _loc2_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc2_.label = "Ваши силы уже полностью восстановлены";
         _loc5_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
      else
      {
         this.equipment.useEatItem();
      }
   }
   function updateHealBtn()
   {
      if(this.equipment.healArr.length > 0)
      {
         this.heal_btn.enabled = true;
      }
      else
      {
         this.heal_btn.enabled = false;
      }
      if(this.equipment.eatArr.length > 0)
      {
         this.eat_btn.enabled = true;
      }
      else
      {
         this.eat_btn.enabled = false;
      }
      this.doLater("updateAmmoNumber");
   }
   function updateAmmoNumber()
   {
      var _loc7_ = this.equipment.primaryItem;
      var _loc6_ = 0;
      var _loc10_;
      var _loc9_;
      var _loc5_;
      var _loc2_;
      var _loc4_;
      var _loc3_;
      var _loc8_;
      if(_loc7_.rootID == lol.core.objects.Item.FIRE_ARM)
      {
         _loc10_ = _loc7_.getProp("ammo_count") == undefined ? "" : _loc7_.getProp("ammo_count");
         _loc9_ = _loc7_.getProp("clip_size") == undefined ? "" : _loc7_.getProp("clip_size");
         _loc5_ = this.equipment.getNumberOfExistAmmo(_loc7_);
         _loc2_ = 0;
         while(_loc2_ < _loc5_.length)
         {
            _loc4_ = _loc5_[_loc2_];
            _loc3_ = _loc4_.getProp("size");
            if(_loc3_)
            {
               _loc6_ += _loc3_;
            }
            else
            {
               _loc4_.addEventListener("itemUpdate",this,this.ammoUpdate);
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc8_ = _loc10_ + "/" + _loc9_ + "(" + _loc6_ + ")";
         this.doLater("showAmount",[_loc8_]);
      }
   }
   function ammoUpdate(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.ammoUpdate);
      this.updateAmmoNumber();
   }
   function heal_func()
   {
      if(this.heal_btn.enabled)
      {
         this.heal();
      }
   }
   function eat_func()
   {
      if(this.eat_btn.enabled)
      {
         this.eat();
      }
   }
   function showHealAP(obj)
   {
      var _loc2_;
      var _loc3_;
      if(obj.target == this.heal_btn)
      {
         _loc3_ = this.equipment.findHealItem();
         _loc2_ = lol.core.objects.HealItem(_loc3_).getAP(lol.core.objects.Item.LOAD);
      }
      else if(obj.target == this.eat_btn)
      {
         _loc3_ = this.equipment.findEatItem();
         _loc2_ = lol.core.objects.HealItem(_loc3_).getAP(lol.core.objects.Item.LOAD);
      }
      lol.core.SceneShifter._ref.currentScene.apBar.otherCost = _loc2_;
      lol.core.SceneShifter._ref.currentScene.apBar.showAPCost();
   }
   function hideHealAP(obj)
   {
      lol.core.SceneShifter._ref.currentScene.apBar.otherCost = 0;
      lol.core.SceneShifter._ref.currentScene.apBar.showAPCost();
      lol.gpui.AnnotationManager.clear();
   }
   function selectFuncKey1()
   {
      if(this.um0_btn.enabled)
      {
         this.um0_btn.toggled = true;
         this.useMode({target:this.um0_btn});
      }
   }
   function selectFuncKey2()
   {
      if(this.um1_btn.enabled)
      {
         this.um1_btn.toggled = true;
         this.useMode({target:this.um1_btn});
      }
   }
   function selectFuncKey3()
   {
      if(this.um2_btn.enabled)
      {
         this.um2_btn.toggled = true;
         this.useMode({target:this.um2_btn});
      }
   }
   function useMode(obj)
   {
      var _loc2_ = obj.target;
      var _loc3_;
      if(this.curMode_btn != _loc2_)
      {
         this.curMode_btn.toggled = false;
         if(_loc2_ == this.um0_btn)
         {
            _loc3_ = 0;
         }
         else if(_loc2_ == this.um1_btn)
         {
            _loc3_ = 1;
         }
         else if(_loc2_ == this.um2_btn)
         {
            _loc3_ = 2;
         }
         this.equipment.changeFireMode(_loc3_);
         this.curMode_btn = _loc2_;
      }
      else
      {
         _loc2_.toggled = true;
      }
   }
   function showUseMode(m)
   {
      this.um0_btn.toggled = false;
      this.um1_btn.toggled = false;
      this.um2_btn.toggled = false;
      this["um" + m + "_btn"].toggled = true;
      this.curMode_btn = this["um" + m + "_btn"];
      var _loc2_ = this.item.getProp("fire_mods");
      this.um0_btn.enabled = Boolean(_loc2_[0]);
      this.um1_btn.enabled = Boolean(_loc2_[1]);
      this.um2_btn.enabled = Boolean(_loc2_[2]);
   }
   function aim(obj)
   {
      var _loc5_ = obj.aim;
      var _loc3_;
      var _loc4_;
      var _loc6_;
      var _loc2_;
      if(_loc5_ == lol.core.player.Gamer.ID)
      {
         _loc3_ = this.equipment.primaryItem;
         if(_loc3_ instanceof lol.core.objects.FireArm)
         {
            _loc4_ = _loc3_.getProp("fire_times");
            _loc6_ = this.item.getProp("cur_mode");
            _loc2_ = _loc4_[_loc6_];
            if(_loc2_)
            {
               this.curType = lol.events.TimeBarEvent.AIM;
               this.startTimeBar(_loc2_);
            }
         }
      }
   }
   function reload(obj)
   {
      this.reloadItem = obj.param;
      var _loc2_ = this.reloadItem.getProp("reload_time");
      var _loc4_ = this.reloadItem.getProp("ammo_count");
      var _loc3_ = this.reloadItem.getProp("clip_size");
      if(_loc2_ && _loc4_ != _loc3_)
      {
         this.reloadItem.addEventListener("itemUpdate",this,this.endTimeBar);
         this.curType = lol.events.TimeBarEvent.RELOAD;
         this.startTimeBar(_loc2_);
         lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.FIREARM_RELOAD);
      }
   }
   function unload(obj)
   {
      this.reloadItem = obj.param;
      var _loc2_ = this.reloadItem.getProp("reload_time");
      if(_loc2_)
      {
         this.reloadItem.addEventListener("itemUpdate",this,this.endTimeBar);
         this.curType = lol.events.TimeBarEvent.UNLOAD;
         this.startTimeBar(_loc2_);
      }
   }
   function healTimeBar(obj)
   {
      this.healItem = obj.param;
      var _loc2_ = this.healItem.getProp("heal_time");
      if(_loc2_)
      {
         this.healItem.addEventListener("itemUpdate",this,this.endTimeBar);
         this.curType = lol.events.TimeBarEvent.HEAL;
         this.startTimeBar(_loc2_);
      }
   }
   function strike(obj)
   {
      this.strikeItem = lol.core.objects.ItemFactory.getItem(obj.target.__usedItem.oID);
      var _loc2_ = this.strikeItem.getProp("strike_time");
      if(_loc2_)
      {
         this.curType = lol.events.TimeBarEvent.STRIKE;
         this.startTimeBar(_loc2_);
      }
   }
   function breakTimeBar(obj)
   {
      if((this.curType == lol.events.TimeBarEvent.AIM || this.curType == lol.events.TimeBarEvent.HEAL || this.curType == lol.events.TimeBarEvent.RELOAD || this.curType == lol.events.TimeBarEvent.UNLOAD || this.curType == lol.events.TimeBarEvent.STRIKE) && obj.id == lol.core.player.Gamer.ID)
      {
         delete this.onEnterFrame;
         delete this.timeBar_mc.onEnterFrame;
         this.curType = null;
         this.timeBar_mc._xscale = 0;
      }
   }
   function endTimeBar(obj)
   {
      if(this.curType == lol.events.TimeBarEvent.STRIKE)
      {
         this.timeBar_mc._xscale = 100;
         this.startEndAnimation();
      }
      else if(this.curType == lol.events.TimeBarEvent.AIM && obj.param == lol.core.player.Gamer.ID)
      {
         this.timeBar_mc._xscale = 100;
         this.startEndAnimation();
      }
      else if((this.curType == lol.events.TimeBarEvent.RELOAD || this.curType == lol.events.TimeBarEvent.UNLOAD) && obj.target.typeID == this.reloadItem.typeID)
      {
         obj.target.removeEventListener("itemUpdate",this,this.endTimeBar);
         this.timeBar_mc._xscale = 100;
         this.startEndAnimation();
      }
      else if(this.curType == lol.events.TimeBarEvent.HEAL && (obj.target.typeID == this.healItem.typeID || obj.target == this.gamer.equipment))
      {
         obj.target.removeEventListener("itemUpdate",this,this.endTimeBar);
         this.timeBar_mc._xscale = 100;
         this.startEndAnimation();
      }
   }
   function startTimeBar(time)
   {
      this.timeBar_mc._xscale = 0;
      this.timeBar_mc._alpha = 100;
      this.animationTime = time;
      this.timeOfStart = getTimer();
      delete this.timeBar_mc.onEnterFrame;
      this.timeBar_mc.onEnterFrame = mx.utils.Delegate.create(this,this.scaleTimeBar);
   }
   function scaleTimeBar()
   {
      if(getTimer() - this.timeOfStart < this.animationTime)
      {
         this.timeBar_mc._xscale = 100 * (getTimer() - this.timeOfStart) / this.animationTime;
      }
      else
      {
         delete this.timeBar_mc.onEnterFrame;
         this.timeBar_mc._xscale = 100;
      }
   }
   function startEndAnimation()
   {
      delete this.timeBar_mc.onEnterFrame;
      this.encreaseAlpha = true;
      this.timeBar_mc.onEnterFrame = mx.utils.Delegate.create(this,this.endAnimation);
   }
   function endAnimation()
   {
      if(this.encreaseAlpha)
      {
         this.timeBar_mc._alpha += 10;
         if(this.timeBar_mc._alpha >= 60)
         {
            this.encreaseAlpha = false;
            this.timeBar_mc._alpha = 60;
         }
      }
      else
      {
         this.timeBar_mc._alpha -= 10;
         if(this.timeBar_mc._alpha <= 0)
         {
            this.timeBar_mc._alpha = 0;
            delete this.timeBar_mc.onEnterFrame;
            this.timeBar_mc._xscale = 0;
         }
      }
   }
}
