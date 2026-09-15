class lol.core.location.Char extends MovieClip
{
   var ___persType;
   var __behavior;
   var __behaviorType;
   var __direction;
   var __fireCount;
   var _id;
   var _pType;
   var burstArr;
   var cont_mc;
   var currentBitmap;
   var currentFrameNumber;
   var deleteEnterFrame;
   var dispatchEvent;
   var driver;
   var isActive;
   var is_default;
   var newEnterFrame;
   var next;
   var numOfShot;
   var onEnterFrame;
   var one_pass_left;
   var warStatus;
   static var STAND = "stand";
   static var RUN = "run";
   static var DAMAGE = "damage";
   static var DIE = "die";
   static var FIRE = "fire";
   static var AIM = "aim";
   static var FIRE_IN = "fire_in";
   static var FIRE_OUT = "fire_out";
   static var ARM_IN = "arm_in";
   static var ARM_OUT = "arm_out";
   static var FALL = "fall";
   static var STANDUP = "standup";
   static var PEACE_TO_MILI = "peace_to_mili";
   static var STAND_MILI = "stand_mili";
   static var MILI_TO_PEACE = "mili_to_peace";
   static var ARM_FIST = "fist";
   static var ARM_PISTOL = "pistol";
   static var ARM_RIFLE = "rifle";
   static var END_OF_SHOT = "END_OF_SHOT";
   var fireCount = 1;
   var lastBType = "fist";
   var nextBType = "fist";
   var locked = false;
   function Char()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      lol.utils.EFBeacon.initialize(this);
      this.cont_mc = this.createEmptyMovieClip("cont_mc",0);
      if(!this.animationEnabled)
      {
         this.loadDefault();
      }
      this.activate(true);
      this.currentFrameNumber = 0;
      this.__direction = 1;
      this.behaviorType = "fist";
      this.behavior = lol.core.location.Char.STAND;
      this.burstArr = new Array();
      this.is_default = true;
      this.one_pass_left = false;
   }
   function get animationEnabled()
   {
      return lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.ANIMATION);
   }
   function get standAnimationEnabled()
   {
      return lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.STAND_ANIMATION);
   }
   function loadDefault()
   {
      var _loc2_ = lol.display.SourceLibrary.getSource("default");
      if(_loc2_.status == null || _loc2_.status == "loading")
      {
         _loc2_.addEventListener("onLoadSource",this,this.loadDefault);
         lol.services.SSEmulator.loadDefault();
      }
      else if(_loc2_.status == "loaded")
      {
         _loc2_.removeEventListener("onLoadSource",this,this.loadDefault);
      }
      var _loc4_ = _loc2_.getBitmap(1);
      var _loc5_ = _loc4_.clone();
      var _loc3_ = _loc2_.getOffset(1);
      this.cont_mc.attachBitmap(_loc5_,0);
      this.cont_mc._x = _loc3_.dx;
      this.cont_mc._y = _loc3_.dy;
   }
   function set id(i)
   {
      this._id = i;
      this.driver = lol.core.Master.getInstance().getPlayer(this.id);
      if(this.player instanceof lol.core.player.Player)
      {
         this.pType = "player";
      }
      else
      {
         this.pType = "mob";
      }
      this.driver.equipment.addEventListener("changePrimary",this,this.changeWeapon);
      this.changeWeapon();
   }
   function get id()
   {
      return this._id;
   }
   function stand()
   {
      this.extendedStand();
      this.startAnimation();
   }
   function extendedStand()
   {
      var _loc2_ = lol.core.Master.getInstance().currentLocation.warStatus;
      if(_loc2_ != this.warStatus)
      {
         this.warStatus = _loc2_;
         if(this.warStatus)
         {
            this.behavior = lol.core.location.Char.PEACE_TO_MILI;
         }
         else
         {
            this.behavior = lol.core.location.Char.MILI_TO_PEACE;
         }
      }
      else
      {
         this.next = lol.core.location.Char.STAND;
         if(this.warStatus)
         {
            this.__behavior = lol.core.location.Char.STAND_MILI;
         }
         else
         {
            this.__behavior = lol.core.location.Char.STAND;
         }
      }
   }
   function run()
   {
      this.next = lol.core.location.Char.RUN;
      this.startAnimation();
   }
   function damage()
   {
      this.next = lol.core.location.Char.STAND;
      this.startAnimation();
   }
   function die()
   {
      this.next = null;
      this.startAnimation();
   }
   function fire()
   {
      if(!this.__fireCount)
      {
         this.__fireCount = !this.fireCount ? 1 : this.fireCount;
      }
      this.__fireCount = this.__fireCount - 1;
      if(this.__fireCount == 0)
      {
         this.next = lol.core.location.Char.FIRE_OUT;
         this.dispatchEvent({type:lol.core.location.Char.END_OF_SHOT,fireCount:this.numOfShot});
      }
      else
      {
         this.next = lol.core.location.Char.FIRE;
      }
      this.startAnimation();
   }
   function aim()
   {
      this.fire_in();
   }
   function fire_in()
   {
      this.next = null;
      this.startAnimation();
   }
   function fire_out()
   {
      this.next = lol.core.location.Char.STAND;
      this.startAnimation();
   }
   function arm_in()
   {
      this.next = lol.core.location.Char.STAND;
      this.startAnimation();
   }
   function arm_out()
   {
      this.next = lol.core.location.Char.STAND;
      this.startAnimation();
   }
   function fall()
   {
      this.behavior = lol.core.location.Char.DIE;
      this.next = lol.core.location.Char.STANDUP;
   }
   function standup()
   {
      this.next = lol.core.location.Char.STAND;
      this.startAnimation();
   }
   function peace_to_mili()
   {
      this.startAnimation();
      this.next = lol.core.location.Char.STAND_MILI;
   }
   function stand_mili()
   {
      this.startAnimation();
      this.next = lol.core.location.Char.STAND;
   }
   function mili_to_peace()
   {
      this.startAnimation();
      this.next = lol.core.location.Char.STAND;
   }
   function set behavior(b)
   {
      if(b != this.__behavior && this.__behavior != lol.core.location.Char.DIE)
      {
         if(this.__behavior == lol.core.location.Char.FIRE)
         {
            this.activate(true);
         }
         this.one_pass_left = false;
         this.__behavior = b;
         this[this.__behavior]();
      }
   }
   function get behavior()
   {
      return this.__behavior;
   }
   function set behaviorType(bt)
   {
      if(bt != this.__behaviorType)
      {
         this.__behaviorType = bt;
      }
   }
   function get behaviorType()
   {
      return this.__behaviorType;
   }
   function changeWeapon(obj)
   {
      var _loc3_;
      var _loc2_;
      if(!obj.changeFireMode)
      {
         _loc3_ = lol.core.Master.getInstance().getPlayer(this.id);
         _loc2_ = _loc3_.primaryItem;
         if(_loc2_.animation_type != undefined)
         {
            if(_loc2_.animation_type != "fist" && this.lastBType != "fist")
            {
               this.behaviorType = this.lastBType;
               this.nextBType = _loc2_.animation_type;
               this.behavior = lol.core.location.Char.ARM_OUT;
               this.next = lol.core.location.Char.ARM_IN;
            }
            else if(this.lastBType == "fist")
            {
               this.weaponON();
            }
            else if(_loc2_.animation_type == "fist")
            {
               this.weaponOFF();
            }
         }
         else if(_loc2_ instanceof lol.core.objects.FireArm)
         {
            _loc2_.addEventListener("itemUpdate",this,this.primItemUpdate);
         }
      }
   }
   function primItemUpdate(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.primItemUpdate);
      this.changeWeapon();
   }
   function weaponON()
   {
      this.behaviorType = this.player.primaryItem.animation_type;
      this.nextBType = this.player.primaryItem.animation_type;
      this.behavior = lol.core.location.Char.ARM_IN;
   }
   function weaponOFF()
   {
      this.behaviorType = this.lastBType;
      this.nextBType = "fist";
      this.behavior = lol.core.location.Char.ARM_OUT;
   }
   function startFirstFrame()
   {
      var _loc4_;
      var _loc2_;
      var _loc3_;
      var _loc5_;
      if(this.isActive && this.animationEnabled)
      {
         this.currentFrameNumber = 0;
         _loc4_ = lol.display.AnimationFactory.getAF(this.pType,this.persType);
         _loc2_ = _loc4_.getFrame(this);
         this.currentBitmap.dispose();
         this.currentBitmap = _loc2_.bitmap;
         _loc3_ = _loc2_.offset;
         _loc5_ = _loc2_.length;
         this.cont_mc.attachBitmap(this.currentBitmap,0);
         this.cont_mc._x = _loc3_.dx;
         this.cont_mc._y = _loc3_.dy;
         this.onEnterFrame = null;
      }
   }
   function startAnimation()
   {
      if(this.isActive && this.animationEnabled)
      {
         this.currentFrameNumber = 0;
         this.onEnterFrame = this.playAnimation;
      }
   }
   function playAnimation()
   {
      var _loc3_ = 1;
      if(this.one_pass_left && this.currentFrameNumber >= 1 && (this.behavior == lol.core.location.Char.STAND || this.behavior == lol.core.location.Char.STAND_MILI) && !this.is_default)
      {
         this.currentFrameNumber = 0;
         this.onEnterFrame = null;
         return undefined;
      }
      var _loc5_;
      var _loc2_;
      var _loc4_;
      if(this.currentFrameNumber == 0 || !this.one_pass_left || this.behavior != lol.core.location.Char.STAND && this.behavior != lol.core.location.Char.STAND_MILI || this.is_default)
      {
         _loc5_ = lol.display.AnimationFactory.getAF(this.pType,this.persType);
         _loc2_ = _loc5_.getFrame(this);
         this.currentBitmap.dispose();
         this.currentBitmap = _loc2_.bitmap;
         _loc4_ = _loc2_.offset;
         _loc3_ = _loc2_.length;
         this.cont_mc.attachBitmap(this.currentBitmap,0);
         this.cont_mc._x = _loc4_.dx;
         this.cont_mc._y = _loc4_.dy;
      }
      this.currentFrameNumber = this.currentFrameNumber + 1;
      if(this.currentFrameNumber >= _loc3_)
      {
         this.dispatchEvent({type:"finalFrame",data:this.__behavior});
         this.nextSequence();
      }
   }
   function nextSequence()
   {
      if(this.next != null)
      {
         if(this.__behavior != this.next)
         {
            this.one_pass_left = false;
         }
         else if(!this.is_default)
         {
            this.one_pass_left = true;
         }
         this.__behavior = this.next;
         this.lastBType = this.behaviorType;
         this.behaviorType = this.nextBType;
         this[this.next]();
      }
      else
      {
         delete this.onEnterFrame;
      }
   }
   function get persType()
   {
      if(this.driver.playerInfo.persType != undefined)
      {
         this.___persType = this.driver.playerInfo.persType;
         return this.driver.playerInfo.persType;
      }
      return this.___persType;
   }
   function get direction()
   {
      return this.__direction;
   }
   function set direction(new_dir)
   {
      var _loc3_;
      var _loc5_;
      var _loc4_;
      if(new_dir != this.__direction && new_dir != undefined)
      {
         this.deleteEnterFrame(this.rotate);
         if(new_dir > this.__direction)
         {
            _loc3_ = new_dir - this.__direction;
            _loc5_ = 8 + this.__direction - new_dir;
         }
         else
         {
            _loc3_ = 8 + new_dir - this.__direction;
            _loc5_ = this.__direction - new_dir;
         }
         if(_loc3_ < _loc5_)
         {
            _loc4_ = 1;
         }
         else
         {
            _loc4_ = -1;
         }
         this.newEnterFrame(this.rotate,new_dir,_loc4_);
      }
   }
   function rotate(new_dir, d)
   {
      this.__direction += d;
      if(this.__direction > 8)
      {
         this.__direction = 1;
      }
      if(this.__direction < 1)
      {
         this.__direction = 8;
      }
      if(this.__direction == new_dir)
      {
         this.deleteEnterFrame(this.rotate);
      }
   }
   function activate(a)
   {
      if(!this.locked)
      {
         if(this.__behavior == lol.core.location.Char.FIRE)
         {
            if(this.animationEnabled)
            {
               this.onEnterFrame = this.playAnimation;
            }
         }
         else if(a != this.isActive)
         {
            this.isActive = a;
            this._visible = a;
            this.behavior = lol.core.location.Char.STAND;
            if(a)
            {
               if(this.animationEnabled)
               {
                  this.onEnterFrame = this.playAnimation;
               }
               if(this.driver.isMob == true)
               {
                  lol.core.SceneShifter.newNPCGameHelpMessage(this.driver.playerInfo.name);
               }
               if(this.driver.isNPC == true)
               {
                  if(this.driver.questType != undefined && !isNaN(this.driver.questType))
                  {
                     lol.core.SceneShifter.newQuestTypeMessage(this.driver.questType);
                  }
                  else
                  {
                     lol.core.SceneShifter.newNPCGameHelpMessage(this.driver.playerInfo.name);
                  }
               }
            }
            else
            {
               delete this.onEnterFrame;
            }
         }
      }
   }
   function get player()
   {
      return lol.core.Master.getInstance().getPlayer(this.id);
   }
   function setPosition(x, y)
   {
      this._x = x;
      this._y = y;
   }
   function set pType(p)
   {
      this._pType = p;
   }
   function get pType()
   {
      return this._pType;
   }
   function fadeDie()
   {
      this.onEnterFrame = function()
      {
         this._alpha -= 3;
         if(this._alpha <= 0)
         {
            delete this.onEnterFrame;
            this.removeMovieClip();
         }
      };
      this.newEnterFrame(this.__fadeDie);
   }
   function __fadeDie()
   {
      this._alpha -= 3;
      if(this._alpha <= 0)
      {
         this.deleteEnterFrame();
         this.removeMovieClip();
      }
   }
   function showCoord()
   {
      var _loc2_ = this.createTextField("coord_txt",this.getNextHighestDepth(),-50,0,100,20);
      _loc2_.textColor = 16777215;
      _loc2_.text = this._x + ":" + this._y;
   }
}
