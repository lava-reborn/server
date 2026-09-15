class lol.services.AutoCommandManager
{
   var XMC;
   var autoFireTargetID;
   var autoShotTargetID;
   var enemyID;
   var gunnerID;
   var warStateBegin;
   var canAutoFire = false;
   var canAutoShot = false;
   var autoFireProcess = false;
   var canFireFlag = true;
   function AutoCommandManager()
   {
      this.init();
   }
   function init()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("faShot",this,this.fireShotHandler);
      this.XMC.addEventListener("faHit",this,this.fireHitHandler);
      this.XMC.addEventListener("caHit",this,this.coldArmHitHandler);
      this.XMC.addEventListener("caMiss",this,this.coldArmMissHandler);
      this.XMC.addEventListener("lch",this);
      this.XMC.addEventListener("c_ap",this);
      this.XMC.addEventListener("userMove",this);
   }
   function kill()
   {
      this.XMC.removeEventListener("faShot",this,this.fireShotHandler);
      this.XMC.removeEventListener("faHit",this,this.fireHitHandler);
      this.XMC.removeEventListener("caHit",this,this.coldArmHitHandler);
      this.XMC.removeEventListener("caMiss",this,this.coldArmMissHandler);
      this.XMC.removeEventListener("lch",this);
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoFireAP);
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoShotAP);
   }
   function c_ap(obj)
   {
      if(this.canAutoFire)
      {
         this.canAutoFire = false;
         this.autoFire();
      }
      else if(this.canAutoShot)
      {
         this.canAutoShot = false;
         this.autoShot();
      }
   }
   function userMove(obj)
   {
      if(obj.param.id == lol.core.player.Gamer.ID)
      {
         this.autoFireTargetDead();
      }
   }
   function lch(obj)
   {
      if(obj.param.enemy)
      {
         this.enemyID = obj.param.enemy;
      }
      if(obj.param.ws != undefined)
      {
         this.warStateHandler(obj);
      }
      if(obj.param.dead == this.autoFireTargetID)
      {
         this.autoFireTargetDead();
      }
      if(obj.param.lostUser == this.autoFireTargetID)
      {
         this.autoFireTargetDead();
      }
   }
   function setTargetID(id)
   {
      this.autoFireTargetID = id;
   }
   function fireShotHandler(obj)
   {
      var _loc3_ = obj.param.status;
      this.gunnerID = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      if(!_loc3_)
      {
         if(this.gunnerID == lol.core.player.Gamer.ID)
         {
            this.canAutoFire = true;
         }
         this.warStateBegin = false;
      }
   }
   function fireHitHandler(obj)
   {
      var _loc4_ = !obj.param.target ? lol.core.player.Gamer.ID : obj.param.target;
      var _loc3_ = !obj.param.dmg ? 0 : obj.param.dmg;
      var _loc5_ = !obj.param.sdmg ? 0 : obj.param.sdmg;
      if(_loc3_ > 0 || _loc5_ > 0)
      {
         if(_loc4_ == lol.core.player.Gamer.ID)
         {
            this.autoShotTargetID = this.gunnerID;
            this.autoShot(this.autoShotTargetID);
         }
      }
   }
   function coldArmHitHandler(obj)
   {
      var _loc3_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc4_ = !obj.param.target ? lol.core.player.Gamer.ID : obj.param.target;
      var _loc5_ = !obj.param.dmg ? 0 : obj.param.dmg;
      var _loc6_ = !obj.param.sdmg ? 0 : obj.param.sdmg;
      if(_loc3_ == lol.core.player.Gamer.ID)
      {
         this.canFireFlag = true;
         this.canAutoFire = true;
      }
      if(_loc4_ == lol.core.player.Gamer.ID)
      {
         this.autoShotTargetID = _loc3_;
         this.autoShot(_loc3_);
      }
      this.warStateBegin = false;
   }
   function coldArmMissHandler(obj)
   {
      var _loc3_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc4_ = -1;
      var _loc5_ = !obj.param.dmg ? 0 : obj.param.dmg;
      var _loc6_ = !obj.param.sdmg ? 0 : obj.param.sdmg;
      if(_loc3_ == lol.core.player.Gamer.ID)
      {
         this.canFireFlag = true;
         this.canAutoFire = true;
      }
      if(_loc4_ == lol.core.player.Gamer.ID)
      {
         this.autoShotTargetID = _loc3_;
         this.autoShot(_loc3_);
      }
      this.warStateBegin = false;
   }
   function warStateHandler(obj)
   {
      if(obj.param.ws != undefined)
      {
         if(obj.param.ws == 1)
         {
            this.warStateBegin = true;
         }
         else
         {
            this.warStateBegin = false;
            this.autoShotTargetID = null;
            this.autoFireTargetID = null;
            this.autoFireProcess = false;
         }
      }
   }
   function attack(id)
   {
      var _loc2_ = new lol.utils.Timeout(this,this._attack,500,id);
   }
   function _attack(id)
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      if(this.canFire() && id)
      {
         if(_loc2_.primaryItem instanceof lol.core.objects.FireArm)
         {
            _loc2_.fire(1,id);
         }
         else if(_loc2_.primaryItem instanceof lol.core.objects.MeleeWeapon)
         {
            _loc2_.gotoWalker(id,"strike");
            _loc2_.strike({id:id,targetCell:lol.core.Master.getInstance().currentLocation.getCellFromNumber(_loc2_.walker.numPos)});
         }
      }
   }
   function autoShot(agressorID)
   {
      var _loc2_;
      var _loc3_;
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_SHOT) && this.checkDistance())
      {
         if(this.canFire())
         {
            _loc2_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
            if(_loc2_ instanceof lol.core.objects.FireArm)
            {
               _loc3_ = lol.core.objects.FireArm(_loc2_);
               this.canAutoShot = !(_loc3_.ammo_count == 0 && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_RELOAD)) ? false : true;
               this.attack(agressorID);
            }
         }
         else
         {
            lol.core.Master.getInstance().gamer.apManager.addEventListener("actionPoints",this,this.autoShotAP);
         }
      }
   }
   function autoShotAP(obj)
   {
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoShotAP);
      this.autoShot();
   }
   function autoFire(targetID)
   {
      var _loc2_;
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_FIRE))
      {
         if(this.checkDistance())
         {
            this.autoFireProcess = true;
            if(this.canFire())
            {
               _loc2_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
               if(fireArm instanceof lol.core.objects.FireArm)
               {
                  var fireArm = lol.core.objects.FireArm(_loc2_);
                  if(fireArm.ammo_count == 0)
                  {
                     if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_RELOAD))
                     {
                        this.canAutoFire = true;
                     }
                     else
                     {
                        this.canAutoFire = false;
                        this.autoFireProcess = false;
                     }
                  }
               }
               this.attack(this.autoFireTargetID);
            }
            else
            {
               lol.core.Master.getInstance().gamer.apManager.addEventListener("actionPoints",this,this.autoFireAP);
            }
         }
         else
         {
            this.autoFireTargetDead();
         }
      }
   }
   function autoFireAP(obj)
   {
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoFireAP);
      this.autoFire();
   }
   function checkDistance()
   {
      var _loc9_ = lol.core.Master.getInstance().currentLocation.getWalker(this.autoFireTargetID);
      var _loc3_ = lol.core.Master.getInstance().currentLocation.getWalker(lol.core.player.Gamer.ID);
      var _loc7_ = _loc9_.x;
      var _loc5_ = _loc9_.y;
      var _loc6_ = _loc3_.x;
      var _loc4_ = _loc3_.y;
      var _loc12_ = (_loc7_ - _loc6_) * (_loc7_ - _loc6_);
      var _loc11_ = (_loc5_ - _loc4_) * (_loc5_ - _loc4_);
      var _loc8_ = Math.sqrt(_loc12_ + _loc11_);
      var _loc10_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
      var _loc2_ = _loc10_.getProp("max_range");
      if(_loc2_)
      {
         if(_loc2_.length > 0)
         {
            if(_loc8_ <= _loc2_[0])
            {
               return true;
            }
         }
         else if(_loc2_ > 0 && _loc2_ >= _loc8_)
         {
            return true;
         }
      }
      return false;
   }
   function canFire()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      var _loc4_ = _loc2_.apManager.ap;
      var _loc7_ = _loc2_.primaryItem.getAP(lol.core.objects.Item.FIRE);
      var _loc1_ = false;
      var _loc3_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
      var _loc5_;
      var _loc6_;
      if(_loc3_ instanceof lol.core.objects.FireArm)
      {
         _loc5_ = lol.core.objects.FireArm(_loc3_);
         _loc6_ = _loc2_.primaryItem.getAP(lol.core.objects.Item.LOAD);
         if(_loc5_.ammo_count == 0)
         {
            if(_loc4_ > _loc6_)
            {
               _loc1_ = true;
            }
         }
         else if(_loc4_ >= _loc7_)
         {
            _loc1_ = true;
         }
      }
      else if(_loc3_ instanceof lol.core.objects.MeleeWeapon)
      {
         _loc1_ = true;
      }
      return _loc1_;
   }
   function autoFireTargetDead()
   {
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoFireAP);
      lol.core.Master.getInstance().gamer.apManager.removeEventListener("actionPoints",this,this.autoShotAP);
      this.canAutoFire = false;
      this.autoFireProcess = false;
      this.autoShotTargetID = null;
      this.autoFireTargetID = null;
      this.autoFireProcess = false;
   }
}
