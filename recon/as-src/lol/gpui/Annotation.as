class lol.gpui.Annotation extends lol.gpui.GPUIObject
{
   var _parent;
   var arrItem;
   var arrLine;
   var attribsTitle;
   var back;
   var back_bottom;
   var back_middle;
   var cont_mc;
   var createEmptyMovieClip;
   var desc_txt;
   var dispatchEvent;
   var getNextHighestDepth;
   var id;
   var item;
   var name_txt;
   var questRewardSize;
   var skillsTitle;
   var specTitle;
   var weightOneObject = false;
   var _fullAnnotation = false;
   var myFlag = false;
   function Annotation()
   {
      super();
      this.arrItem = new Array();
      this.arrLine = new Array();
      this.cont_mc = this.createEmptyMovieClip("cont_mc",this.getNextHighestDepth());
      this.cont_mc._x = 13;
      this.cont_mc._visible = false;
      this.name_txt.autoSize = true;
      this.desc_txt.autoSize = true;
      this.desc_txt.html = true;
      this.doLater("init");
      this.attribsTitle = new Array();
      this.attribsTitle = ["Сила","Ловкость","Телосложение","Восприятие","Интеллект"];
      this.skillsTitle = new Array();
      this.skillsTitle = ["Ближний бой","Стрельба","Медицина","Промышленность","Производство"];
      this.specTitle = new Array();
      this.specTitle = ["Рукопашный бой","Режущее оружие","Пистолеты","Дробовики","Автоматы","Винтовки","Ручные пулеметы","Пистолет-пулеметы","Хирургия","Первая помощь","Добыча","Переработка","UC1","UC2","UC3"];
   }
   function init()
   {
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CTRL,this,this.showFullAnnotation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SHIFT,this,this.showMyAnnotation);
      this.back_bottom = this.back.back_bottom;
      this.back_middle = this.back.back_middle;
      this.back_bottom.close_btn.addEventListener("click",this);
   }
   function kill()
   {
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CTRL,this,this.showFullAnnotation);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SHIFT,this,this.showMyAnnotation);
   }
   function backOnPress()
   {
      lol.core.SceneShifter.sortWindows("annotation",this._parent._parent);
   }
   function click()
   {
      this.dispatchEvent({type:"close"});
      lol.core.SceneShifter.closeWindow("annotation",this._parent._parent);
   }
   function set fullAnnotation(value)
   {
      this._fullAnnotation = value;
      this.__showInfo();
   }
   function get fullAnnotation()
   {
      return this._fullAnnotation;
   }
   function showFullAnnotation()
   {
      if(!this.fullAnnotation)
      {
         this.fullAnnotation = true;
      }
   }
   function showMyAnnotation()
   {
      var _loc2_;
      if(!this.myFlag)
      {
         _loc2_ = lol.gpui.AnnotationManager.getMyItem(this.item);
         if(_loc2_)
         {
            this.myFlag = true;
            this.showFullAnnotation();
            lol.gpui.AnnotationManager.createSec(_loc2_,true,true);
         }
      }
   }
   function showInfo(_item, full, _my)
   {
      this._fullAnnotation = full;
      if(_my)
      {
         this.back.my_mc._alpha = 100;
         this.myFlag = true;
      }
      if(full)
      {
         lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CTRL,this,this.showFullAnnotation);
      }
      this.item = _item;
      this.id = this.item.id;
      this.__showInfo();
   }
   function showEffectsInfo(effects, effects_prob, full, _my)
   {
      this._fullAnnotation = full;
      if(_my)
      {
         this.back.my_mc._alpha = 100;
         this.myFlag = true;
      }
      if(full)
      {
         lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CTRL,this,this.showFullAnnotation);
      }
      this.cont_mc.removeMovieClip();
      this.cont_mc = this.createEmptyMovieClip("cont_mc",this.getNextHighestDepth());
      this.cont_mc._x = 13;
      var _loc16_ = new TextFormat();
      _loc16_.bold = true;
      this.name_txt.htmlText = "ЭФФЕКТЫ";
      this.name_txt.setTextFormat(_loc16_);
      var _loc18_ = new Array();
      this.arrItem = new Array();
      this.arrLine = new Array();
      var _loc19_ = 0;
      var _loc6_ = 0;
      var _loc2_;
      var _loc4_;
      var _loc11_;
      var _loc13_;
      var _loc10_;
      var _loc12_;
      var _loc3_;
      var _loc7_;
      var _loc8_;
      var _loc9_;
      var _loc5_;
      while(_loc6_ < effects.length)
      {
         _loc2_ = lol.core.effects.Effect(effects[_loc6_]);
         if(_loc2_)
         {
            _loc4_ = this.cont_mc.attachMovie("effect_title","effect_title",this.cont_mc.getNextHighestDepth());
            _loc11_ = this.cont_mc.attachMovie("annotation_line","annotation_line",this.cont_mc.getNextHighestDepth());
            _loc4_.effect_name.autoSize = true;
            _loc4_.effect_name.html = true;
            _loc13_ = _loc2_.name;
            _loc4_.effect_name.htmlText = _loc13_;
            _loc4_.effect_prob.autoSize = true;
            _loc4_.effect_prob.html = true;
            _loc10_ = effects_prob[_loc6_].toString();
            _loc4_.effect_prob.htmlText = "Вероятность срабатывания: " + _loc10_;
            _loc4_.effect_prob._y = _loc4_.effect_name._y + _loc4_.effect_name._height + 1;
            _loc12_ = lol.services.SSEmulator.getEffectIcon(_loc2_.res_icon);
            _loc4_.effect_icon = lol.display.DisplaySprite.create(_loc4_,_loc6_ + "_effect_icon",0);
            _loc4_.effect_icon.autoSize = false;
            _loc4_.effect_icon.display(_loc6_ + "_effect_icon",_loc12_);
            this.arrItem.push(_loc4_);
            this.arrLine.push(_loc11_);
            _loc3_ = new Array();
            _loc3_.push(["Время действия",lol.gpui.Annotation.getTextDuration(_loc2_.work_time)]);
            if(_loc2_.update_delta && _loc2_.update_delta != NaN)
            {
               _loc3_.push(["Интервал активации",lol.gpui.Annotation.getTextDuration(_loc2_.update_delta)]);
            }
            _loc8_ = _loc2_.bonusAttribs;
            _loc7_ = this.readArray(_loc8_,this.attribsTitle);
            _loc3_.push(["Бонусы\rк аттрибутам",_loc7_]);
            _loc8_ = _loc2_.bonusSkills;
            _loc7_ = this.readArray(_loc8_,this.skillsTitle);
            _loc3_.push(["Бонусы\rк навыкам",_loc7_]);
            _loc8_ = _loc2_.bonusSpecs;
            _loc7_ = this.readArray(_loc8_,this.specTitle);
            _loc3_.push(["Бонусы\rк специализациям",_loc7_]);
            _loc3_.push(["Бонус к здоровью",_loc2_.max_hp]);
            _loc3_.push(["Бонус к выносливости",_loc2_.max_sp]);
            if(!isNaN(_loc2_.max_od) && _loc2_.max_od > 0)
            {
               _loc3_.push(["Бонус\rк очкам действия",_loc2_.max_od * 2]);
            }
            _loc3_.push(["Бонус\rк критическому попаданию",_loc2_.critical_probability]);
            _loc3_.push(["Бонус\rк избеганию крита",_loc2_.critical_evade]);
            _loc3_.push(["Бонус к броне",_loc2_.armor]);
            if(!isNaN(_loc2_.mob_exp))
            {
               if(_loc2_.mob_exp > 1)
               {
                  _loc3_.push(["Бонус\rк опыту с мобов",(1 - _loc2_.mob_exp) * 100 + "%"]);
               }
               else if(_loc2_.mob_exp < 1)
               {
                  _loc3_.push(["Штраф\rк опыту с мобов",(1 - _loc2_.mob_exp) * 100 + "%"]);
               }
            }
            if(!isNaN(_loc2_.player_exp))
            {
               if(_loc2_.player_exp > 1)
               {
                  _loc3_.push(["Бонус\rк опыту с игроков",(1 - _loc2_.player_exp) * 100 + "%"]);
               }
               else if(_loc2_.player_exp < 1)
               {
                  _loc3_.push(["Штраф\rк опыту с игроков",(1 - _loc2_.player_exp) * 100 + "%"]);
               }
            }
            if(!isNaN(_loc2_.mob_drop))
            {
               _loc9_ = Math.round(1 / _loc2_.mob_drop * 100 / 1 - 100);
               if(_loc2_.mob_drop < 1)
               {
                  _loc3_.push(["Бонус\rк луту с мобов",_loc9_ + "%"]);
               }
               else if(_loc2_.mob_drop > 1)
               {
                  _loc3_.push(["Штраф\rк луту с мобов",_loc9_ + "%"]);
               }
            }
            if(_loc2_.player_drop != 1 && !isNaN(_loc2_.player_drop))
            {
               _loc3_.push(["Защита вашего дропа",(1 - _loc2_.player_drop) * 100 + "%"]);
            }
            _loc5_ = 0;
            while(_loc5_ < _loc3_.length)
            {
               this.addItem(_loc3_[_loc5_][0],_loc3_[_loc5_][1]);
               _loc5_ = _loc5_ + 1;
            }
         }
         _loc6_ = _loc6_ + 1;
      }
      this.doLater("align");
   }
   function effectAnnotation(effect)
   {
      var _loc5_;
      var _loc2_ = new Array();
      if(this._fullAnnotation)
      {
         this.addDesc(_loc2_);
      }
      _loc2_.push(["Время действия",lol.gpui.Annotation.getTextDuration(effect.work_time)]);
      if(effect.update_delta && effect.update_delta != NaN)
      {
         _loc2_.push(["Интервал активации",lol.gpui.Annotation.getTextDuration(effect.update_delta)]);
      }
      var _loc6_ = effect.bonusAttribs;
      _loc5_ = this.readArray(_loc6_,this.attribsTitle);
      _loc2_.push(["Бонусы\rк аттрибутам",_loc5_]);
      _loc6_ = effect.bonusSkills;
      _loc5_ = this.readArray(_loc6_,this.skillsTitle);
      _loc2_.push(["Бонусы\rк навыкам",_loc5_]);
      _loc6_ = effect.bonusSpecs;
      _loc5_ = this.readArray(_loc6_,this.specTitle);
      _loc2_.push(["Бонусы\rк специализациям",_loc5_]);
      _loc2_.push(["Бонус к здоровью",effect.max_hp]);
      _loc2_.push(["Бонус к выносливости",effect.max_sp]);
      if(!isNaN(effect.max_od) && effect.max_od > 0)
      {
         _loc2_.push(["Бонус\rк очкам действия",effect.max_od * 2]);
      }
      _loc2_.push(["Бонус\rк критическому попаданию",effect.critical_probability]);
      _loc2_.push(["Бонус\rк избеганию крита",effect.critical_evade]);
      _loc2_.push(["Бонус к броне",effect.armor]);
      if(!isNaN(effect.mob_exp))
      {
         if(effect.mob_exp > 1)
         {
            _loc2_.push(["Бонус\rк опыту с мобов",(1 - effect.mob_exp) * 100 + "%"]);
         }
         else if(effect.mob_exp < 1)
         {
            _loc2_.push(["Штраф\rк опыту с мобов",(1 - effect.mob_exp) * 100 + "%"]);
         }
      }
      if(!isNaN(effect.player_exp))
      {
         if(effect.player_exp > 1)
         {
            _loc2_.push(["Бонус\rк опыту с игроков",(1 - effect.player_exp) * 100 + "%"]);
         }
         else if(effect.player_exp < 1)
         {
            _loc2_.push(["Штраф\rк опыту с игроков",(1 - effect.player_exp) * 100 + "%"]);
         }
      }
      var _loc7_;
      if(!isNaN(effect.mob_drop))
      {
         _loc7_ = Math.round(1 / effect.mob_drop * 100 / 1 - 100);
         if(effect.mob_drop < 1)
         {
            _loc2_.push(["Бонус\rк луту с мобов",_loc7_ + "%"]);
         }
         else if(effect.mob_drop > 1)
         {
            _loc2_.push(["Штраф\rк луту с мобов",_loc7_ + "%"]);
         }
      }
      if(effect.player_drop != 1 && !isNaN(effect.player_drop))
      {
         _loc2_.push(["Защита вашего дропа",(1 - effect.player_drop) * 100 + "%"]);
      }
      var _loc3_ = 0;
      while(_loc3_ < _loc2_.length)
      {
         this.addItem(_loc2_[_loc3_][0],_loc2_[_loc3_][1]);
         _loc3_ = _loc3_ + 1;
      }
   }
   function __showInfo()
   {
      this.arrItem = new Array();
      this.arrLine = new Array();
      this.cont_mc.removeMovieClip();
      this.cont_mc = this.createEmptyMovieClip("cont_mc",this.getNextHighestDepth());
      this.cont_mc._x = 13;
      var _loc4_ = this.item.getProp("name");
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.name_txt.htmlText = _loc4_.toUpperCase();
      if(this.item.rootID == lol.core.objects.Item.TROPHY && lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY))
      {
         this.name_txt.htmlText = "ТРОФЕЙ";
      }
      this.name_txt.setTextFormat(_loc2_);
      var _loc3_;
      if(this.item instanceof lol.core.effects.Effect)
      {
         _loc3_ = this.item;
         this.name_txt.htmlText = _loc3_.name;
         this.effectAnnotation(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.FIRE_ARM)
      {
         this.fireArm(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.COLD_ARM)
      {
         this.coldArm(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.WEAR)
      {
         this.wear(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.HEAL_ITEM)
      {
         this.healItem(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.AMMO)
      {
         this.ammo(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.TRASH)
      {
         this.trash(this.item);
      }
      else if(this.item.rootID == lol.core.objects.Item.TROPHY)
      {
         this.trophy(this.item);
      }
      else if(this.item.rootID == lol.core.transport.TransObject.TRANSPORT)
      {
         this.transport(this.item);
      }
      else if(this.item instanceof lol.core.sets.SetObject)
      {
         this.sets(this.item);
      }
      if(!this.fullAnnotation)
      {
         this.addItem("<font color=\'#665e54\'>Для просмотра полного\rописания нажмите CTRL</font>","");
      }
      this.doLater("align");
   }
   function create_bonus_str(bonus)
   {
      if(bonus > 0)
      {
         return String("+" + bonus);
      }
      return String(bonus);
   }
   function fireArm(item)
   {
      var _loc7_ = new Array();
      if(this.fullAnnotation)
      {
         _loc7_.push([item.getProp("desc") + "\r\r",""]);
      }
      var _loc5_ = "";
      var _loc15_ = item.getProp("need_attribs");
      _loc5_ = this.readArray(_loc15_,this.attribsTitle);
      _loc7_.push(["Необходимые\rаттрибуты",_loc5_]);
      _loc15_ = item.getProp("need_skills");
      _loc5_ = this.readArray(_loc15_,this.skillsTitle);
      _loc7_.push(["Необходимые\rнавыки",_loc5_]);
      _loc15_ = item.getProp("need_specs");
      _loc5_ = this.readArray(_loc15_,this.specTitle);
      _loc7_.push(["Необходимые\rспециализации",_loc5_]);
      _loc7_.push(["Необходимый навык бойца",item.getProp("need_pvp_rep")]);
      var _loc14_ = lol.core.Master.getInstance().gamer.equipment.getAmmo(item);
      _loc5_ = "\r";
      var _loc19_ = item.getProp("ammo_type");
      var _loc12_;
      var _loc13_ = false;
      var _loc11_ = false;
      var _loc10_ = 0;
      var _loc9_;
      var _loc6_;
      var _loc8_;
      while(_loc10_ < _loc14_.length)
      {
         _loc9_ = _loc14_[_loc10_];
         if(_loc9_.inited)
         {
            _loc6_ = _loc9_.getProp("name");
            _loc8_ = _loc9_.getProp("mod_type");
            _loc11_ = _loc8_ != undefined;
            if(_loc12_ != _loc6_ && _loc6_ != undefined)
            {
               if(_loc12_)
               {
                  if(_loc13_)
                  {
                     _loc5_ += ")";
                  }
                  _loc5_ += "\r" + _loc6_;
               }
               else
               {
                  _loc5_ += "\r" + _loc6_;
               }
               if(_loc11_)
               {
                  if(_loc12_ != _loc6_)
                  {
                     _loc5_ += " (" + _loc8_;
                  }
                  else
                  {
                     _loc5_ += ", " + _loc8_;
                  }
               }
               _loc13_ = _loc11_;
               _loc12_ = _loc6_;
            }
            else if(_loc8_ != undefined)
            {
               _loc11_ = true;
               _loc13_ = _loc11_;
               _loc5_ += ", " + _loc8_;
            }
         }
         else
         {
            _loc9_.addEventListener("itemUpdate",this,this.__showInfo);
         }
         _loc10_ = _loc10_ + 1;
      }
      if(_loc11_)
      {
         _loc5_ += ")";
      }
      _loc7_.push(["Подходящие типы патронов",_loc5_]);
      var _loc18_ = !item.getProp("ammo_count") ? "0" : item.getProp("ammo_count");
      var _loc17_ = !item.getProp("clip_size") ? "?" : item.getProp("clip_size");
      _loc5_ = _loc18_ + " / " + _loc17_;
      _loc7_.push(["Количество патронов",_loc5_]);
      var _loc16_;
      var _loc4_;
      var _loc3_;
      if(this.fullAnnotation)
      {
         _loc16_ = item.getProp("fire_mods");
         _loc10_ = 0;
         while(_loc10_ < _loc16_.length)
         {
            if(item.getProp("fire_mods")[_loc10_])
            {
               _loc4_ = "Режим " + (_loc10_ + 1);
               if(item.getProp("h_damage_max")[_loc10_] != 0)
               {
                  _loc4_ += "\r - урон по здоровью";
               }
               if(item.getProp("st_damage_max")[_loc10_] != 0)
               {
                  _loc4_ += "\r - урон по выносливости";
               }
               if(item.getProp("accuracy")[_loc10_] != 0)
               {
                  _loc4_ += "\r - разброс на 100 м";
               }
               if(item.getProp("max_range")[_loc10_] != 0)
               {
                  _loc4_ += "\r - максимальная дистанция";
               }
               if(item.getProp("end_opt_range")[_loc10_] != 0)
               {
                  _loc4_ += "\r - оптимальная";
               }
               if(item.getProp("piercing")[_loc10_] != 0)
               {
                  _loc4_ += "\r - бронебойность";
               }
               _loc4_ += "\r - длина очереди";
               if(item.getProp("fire_times")[_loc10_] != 0)
               {
                  _loc4_ += "\r - время на изготовку";
               }
               _loc4_ += "\r - очки действия";
               _loc3_ = "";
               if(item.getProp("h_damage_max")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("h_damage_min")[_loc10_] + "-" + item.getProp("h_damage_max")[_loc10_];
               }
               if(item.getProp("st_damage_max")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("st_damage_min")[_loc10_] + "-" + item.getProp("st_damage_max")[_loc10_];
               }
               if(item.getProp("accuracy")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("accuracy")[_loc10_];
               }
               if(item.getProp("max_range")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("max_range")[_loc10_];
               }
               if(item.getProp("end_opt_range")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("opt_range")[_loc10_] + "-" + item.getProp("end_opt_range")[_loc10_];
               }
               if(item.getProp("piercing")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("piercing")[_loc10_];
               }
               _loc3_ += "\r" + item.getProp("fire_mods")[_loc10_];
               if(item.getProp("fire_times")[_loc10_] != 0)
               {
                  _loc3_ += "\r" + item.getProp("fire_times")[_loc10_] / 1000 + " c";
               }
               _loc3_ += "\r" + item.getProp("fire_costs")[_loc10_];
               _loc7_.push([_loc4_,_loc3_]);
            }
            _loc10_ = _loc10_ + 1;
         }
         _loc15_ = item.getProp("bonus_attribs");
         _loc5_ = this.readArray(_loc15_,this.attribsTitle);
         _loc7_.push(["Бонусы\rк аттрибутам",_loc5_]);
         _loc15_ = item.getProp("bonus_skills");
         _loc5_ = this.readArray(_loc15_,this.skillsTitle);
         _loc7_.push(["Бонусы\rк навыкам",_loc5_]);
         _loc15_ = item.getProp("bonus_specs");
         _loc5_ = this.readArray(_loc15_,this.specTitle);
         _loc7_.push(["Бонусы\rк специализациям",_loc5_]);
         if(item.getProp("bonus_hp"))
         {
            _loc7_.push(["Здоровье",this.create_bonus_str(item.getProp("bonus_hp"))]);
         }
         if(item.getProp("bonus_st"))
         {
            _loc7_.push(["Выносливость",this.create_bonus_str(item.getProp("bonus_st"))]);
         }
         if(item.getProp("bonus_od"))
         {
            _loc7_.push(["Очки действия",this.create_bonus_str(item.getProp("bonus_od"))]);
         }
         if(item.getProp("bonus_cp"))
         {
            _loc7_.push(["Крит. попадание",this.create_bonus_str(item.getProp("bonus_cp"))]);
         }
         if(item.getProp("bonus_ce"))
         {
            _loc7_.push(["Избег. крит. попадания",this.create_bonus_str(item.getProp("bonus_ce"))]);
         }
         _loc7_.push(["Износ",this.breakString(item)]);
         this.addExchange(_loc7_);
         this.addSell(_loc7_);
         _loc7_.push(["Вес",item.getProp("_weight") + " г"]);
         this.addCost(_loc7_);
      }
      _loc10_ = 0;
      while(_loc10_ < _loc7_.length)
      {
         this.addItem(_loc7_[_loc10_][0],_loc7_[_loc10_][1]);
         _loc10_ = _loc10_ + 1;
      }
   }
   function showAmmoInfo(item, annotationArr)
   {
      var _loc5_ = lol.core.Master.getInstance().gamer.equipment.getAmmo(item);
      var _loc6_ = "";
      var _loc1_ = 0;
      var _loc3_;
      var _loc2_;
      var _loc4_;
      while(_loc1_ < _loc5_.length)
      {
         _loc3_ = _loc5_[_loc1_];
         _loc2_ = _loc3_.getProp("name");
         _loc4_ = _loc3_.getProp("mod_type");
         _loc6_ += !_loc4_ ? _loc2_ + "\r" : _loc2_ + " " + _loc4_ + "\r";
         _loc1_ = _loc1_ + 1;
      }
      annotationArr.push(["Подходящие \rтипы патронов",_loc6_]);
   }
   function coldArm(item)
   {
      var _loc2_ = new Array();
      if(this.fullAnnotation)
      {
         this.addDesc(_loc2_);
      }
      if(item.getProp("h_damage_max") != 0)
      {
         _loc2_.push(["Урон по здоровью",item.getProp("h_damage_min") + "-" + item.getProp("h_damage_max")]);
      }
      if(item.getProp("st_damage_max") != 0)
      {
         _loc2_.push(["Урон по выносливости",item.getProp("st_damage_min") + "-" + item.getProp("st_damage_max")]);
      }
      _loc2_.push(["Максимальная дистанция",item.getProp("max_range")]);
      _loc2_.push(["Очки действия",item.getProp("strike_cost")]);
      var _loc6_ = item.getProp("need_attribs");
      var _loc5_ = this.readArray(_loc6_,this.attribsTitle);
      _loc2_.push(["Необходимые аттрибуты",_loc5_]);
      _loc6_ = item.getProp("need_skills");
      _loc5_ = this.readArray(_loc6_,this.skillsTitle);
      _loc2_.push(["Необходимые навыки",_loc5_]);
      _loc6_ = item.getProp("need_specs");
      _loc5_ = this.readArray(_loc6_,this.specTitle);
      _loc2_.push(["Необходимые специализации",_loc5_]);
      _loc2_.push(["Необходимый навык бойца",item.getProp("need_pvp_rep")]);
      _loc6_ = item.getProp("bonus_attribs");
      _loc5_ = this.readArray(_loc6_,this.attribsTitle);
      _loc2_.push(["Бонусы к аттрибутам",_loc5_]);
      _loc6_ = item.getProp("bonus_skills");
      _loc5_ = this.readArray(_loc6_,this.skillsTitle);
      _loc2_.push(["Бонусы к навыкам",_loc5_]);
      _loc6_ = item.getProp("bonus_specs");
      _loc5_ = this.readArray(_loc6_,this.specTitle);
      _loc2_.push(["Бонусы к специализациям",_loc5_]);
      if(item.getProp("bonus_hp"))
      {
         _loc2_.push(["Здоровье",this.create_bonus_str(item.getProp("bonus_hp"))]);
      }
      if(item.getProp("bonus_st"))
      {
         _loc2_.push(["Выносливость",this.create_bonus_str(item.getProp("bonus_st"))]);
      }
      if(item.getProp("bonus_od"))
      {
         _loc2_.push(["Очки действия",this.create_bonus_str(item.getProp("bonus_od"))]);
      }
      if(item.getProp("bonus_cp"))
      {
         _loc2_.push(["Крит. попадание",this.create_bonus_str(item.getProp("bonus_cp"))]);
      }
      if(item.getProp("bonus_ce"))
      {
         _loc2_.push(["Избег. крит. попадания",this.create_bonus_str(item.getProp("bonus_ce"))]);
      }
      if(this.fullAnnotation)
      {
         _loc2_.push(["Износ",this.breakString(item)]);
         this.addExchange(_loc2_);
         this.addSell(_loc2_);
         _loc2_.push(["Вес",item.getProp("_weight") + " г"]);
         this.addCost(_loc2_);
      }
      var _loc3_ = 0;
      while(_loc3_ < _loc2_.length)
      {
         this.addItem(_loc2_[_loc3_][0],_loc2_[_loc3_][1]);
         _loc3_ = _loc3_ + 1;
      }
   }
   function wear(item)
   {
      var _loc2_ = new Array();
      if(this.fullAnnotation)
      {
         this.addDesc(_loc2_);
      }
      _loc2_.push(["Уровень брони",item.getProp("armor_class")]);
      var _loc6_ = item.getProp("need_attribs");
      var _loc4_ = this.readArray(_loc6_,this.attribsTitle);
      _loc2_.push(["Необходимые\rаттрибуты",_loc4_]);
      _loc6_ = item.getProp("need_skills");
      _loc4_ = this.readArray(_loc6_,this.skillsTitle);
      _loc2_.push(["Необходимые\rнавыки",_loc4_]);
      _loc6_ = item.getProp("need_specs");
      _loc4_ = this.readArray(_loc6_,this.specTitle);
      _loc2_.push(["Необходимые\rспециализации",_loc4_]);
      _loc2_.push(["Необходимый навык бойца",item.getProp("need_pvp_rep")]);
      _loc6_ = item.getProp("bonus_attribs");
      _loc4_ = this.readArray(_loc6_,this.attribsTitle);
      _loc2_.push(["Бонусы\rк аттрибутам",_loc4_]);
      _loc6_ = item.getProp("bonus_skills");
      _loc4_ = this.readArray(_loc6_,this.skillsTitle);
      _loc2_.push(["Бонусы\rк навыкам",_loc4_]);
      _loc6_ = item.getProp("bonus_specs");
      _loc4_ = this.readArray(_loc6_,this.specTitle);
      _loc2_.push(["Бонусы\rк специализациям",_loc4_]);
      if(item.getProp("bonus_hp"))
      {
         _loc2_.push(["Здоровье",this.create_bonus_str(item.getProp("bonus_hp"))]);
      }
      if(item.getProp("bonus_st"))
      {
         _loc2_.push(["Выносливость",this.create_bonus_str(item.getProp("bonus_st"))]);
      }
      if(item.getProp("bonus_od"))
      {
         _loc2_.push(["Очки действия",this.create_bonus_str(item.getProp("bonus_od"))]);
      }
      if(item.getProp("bonus_cp"))
      {
         _loc2_.push(["Крит. попадание",this.create_bonus_str(item.getProp("bonus_cp"))]);
      }
      if(item.getProp("bonus_ce"))
      {
         _loc2_.push(["Избег. крит.\rпопадания",this.create_bonus_str(item.getProp("bonus_ce"))]);
      }
      if(this.fullAnnotation)
      {
         _loc4_ = item.getProp("slot_type");
         switch(_loc4_)
         {
            case 0:
               _loc4_ = "Головной убор";
               break;
            case 1:
               _loc4_ = "Верхняя одежда";
               break;
            case 2:
               _loc4_ = "Броня";
               break;
            case 3:
               _loc4_ = "Пояс";
               break;
            case 4:
               _loc4_ = "Штаны";
               break;
            case 5:
               _loc4_ = "Ботинки";
         }
         _loc2_.push(["Тип",_loc4_]);
         _loc2_.push(["Износ",this.breakString(item)]);
         this.addExchange(_loc2_);
         this.addSell(_loc2_);
         _loc2_.push(["Вес",item.getProp("_weight") + " г"]);
         this.addCost(_loc2_);
      }
      var _loc3_ = 0;
      while(_loc3_ < _loc2_.length)
      {
         this.addItem(_loc2_[_loc3_][0],_loc2_[_loc3_][1]);
         _loc3_ = _loc3_ + 1;
      }
   }
   function sets(item)
   {
      var _loc12_ = new Array();
      var _loc13_ = item.typeID;
      this.addDesc(_loc12_);
      var _loc8_ = 2;
      var _loc11_;
      var _loc3_;
      var _loc4_;
      var _loc7_;
      var _loc6_;
      var _loc5_;
      var _loc9_;
      var _loc10_;
      while(_loc8_ < 7)
      {
         _loc11_ = "<B>Комплект из " + _loc8_ + " предметов</B>";
         _loc3_ = " ";
         if(item["bonus_" + _loc8_ + "_hp"])
         {
            _loc3_ += "<BR> Здоровье";
         }
         if(item["bonus_" + _loc8_ + "_st"])
         {
            _loc3_ += "<BR> Выносливость";
         }
         if(item["bonus_" + _loc8_ + "_od"])
         {
            _loc3_ += "<BR> Очки действия";
         }
         if(item["bonus_" + _loc8_ + "_cp"])
         {
            _loc3_ += "<BR> Крит. попадание";
         }
         if(item["bonus_" + _loc8_ + "_ce"])
         {
            _loc3_ += "<BR> Избег. крит. попадания";
         }
         _loc4_ = " ";
         if(item["bonus_" + _loc8_ + "_hp"])
         {
            _loc4_ += (item["bonus_" + _loc8_ + "_hp"] <= 0 ? "<BR>" : "<BR>+") + item["bonus_" + _loc8_ + "_hp"];
         }
         if(item["bonus_" + _loc8_ + "_st"])
         {
            _loc4_ += (item["bonus_" + _loc8_ + "_st"] <= 0 ? "<BR>" : "<BR>+") + item["bonus_" + _loc8_ + "_st"];
         }
         if(item["bonus_" + _loc8_ + "_od"])
         {
            _loc4_ += (item["bonus_" + _loc8_ + "_od"] <= 0 ? "<BR>" : "<BR>+") + item["bonus_" + _loc8_ + "_od"];
         }
         if(item["bonus_" + _loc8_ + "_cp"])
         {
            _loc4_ += (item["bonus_" + _loc8_ + "_cp"] <= 0 ? "<BR>" : "<BR>+") + item["bonus_" + _loc8_ + "_cp"];
         }
         if(item["bonus_" + _loc8_ + "_ce"])
         {
            _loc4_ += (item["bonus_" + _loc8_ + "_ce"] <= 0 ? "<BR>" : "<BR>+") + item["bonus_" + _loc8_ + "_ce"];
         }
         _loc7_ = item["bonus_" + _loc8_ + "_skills"];
         _loc6_ = this.skillsTitle.length;
         _loc5_ = 0;
         while(_loc5_ < _loc6_)
         {
            if(_loc7_[_loc5_])
            {
               _loc3_ += "<BR> " + this.skillsTitle[_loc5_];
               _loc4_ += "<BR>+" + _loc7_[_loc5_];
            }
            _loc5_ = _loc5_ + 1;
         }
         _loc9_ = item["bonus_" + _loc8_ + "_specs"];
         _loc6_ = this.specTitle.length;
         _loc5_ = 0;
         while(_loc5_ < _loc6_)
         {
            if(_loc9_[_loc5_])
            {
               _loc3_ += "<BR> " + this.specTitle[_loc5_];
               _loc4_ += "<BR>+" + _loc9_[_loc5_];
            }
            _loc5_ = _loc5_ + 1;
         }
         _loc10_ = item["bonus_" + _loc8_ + "_attribs"];
         _loc6_ = this.attribsTitle.length;
         _loc5_ = 0;
         while(_loc5_ < _loc6_)
         {
            if(_loc10_[_loc5_])
            {
               _loc3_ += "<BR> " + this.attribsTitle[_loc5_];
               _loc4_ += "<BR>+" + _loc10_[_loc5_];
            }
            _loc5_ = _loc5_ + 1;
         }
         if(lol.core.Master.getInstance().gamer.equipment.getNumOfSetItem(_loc13_) >= _loc8_)
         {
            _loc11_ = "<font color=\'#D7B631\'>" + _loc11_ + "</font>";
         }
         if(_loc3_ != " ")
         {
            _loc12_.push([_loc11_ + _loc3_,_loc4_]);
         }
         _loc8_ = _loc8_ + 1;
      }
      _loc8_ = 0;
      while(_loc8_ < _loc12_.length)
      {
         this.addItem(_loc12_[_loc8_][0],_loc12_[_loc8_][1]);
         _loc8_ = _loc8_ + 1;
      }
   }
   function trash(item)
   {
      var _loc3_ = new Array();
      var _loc6_ = lol.core.objects.Heapable(item);
      var _loc4_ = !this.weightOneObject ? item.getProp("weight") : item.getProp("_weight");
      if(this.fullAnnotation)
      {
         this.addDesc(_loc3_);
         this.addExchange(_loc3_);
         this.addSell(_loc3_);
         _loc3_.push(["Вес",_loc4_ + " г"]);
         this.addCost(_loc3_);
      }
      else
      {
         _loc3_.push(["Вес",_loc4_ + " г"]);
         this.addCost(_loc3_);
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.addItem(_loc3_[_loc2_][0],_loc3_[_loc2_][1]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function trophy(item)
   {
      var _loc3_ = new Array();
      if(!lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY) && this.fullAnnotation)
      {
         this.addDesc(_loc3_);
      }
      var _loc7_ = lol.core.objects.Heapable(item);
      var _loc6_ = !this.weightOneObject ? item.getProp("weight") : item.getProp("_weight");
      _loc3_.push(["Вес",_loc6_ + " г"]);
      this.addExchange(_loc3_);
      _loc3_.push(["Допустимость продажи","Нет"]);
      _loc3_.push(["Количество",item.getProp("count")]);
      _loc3_.push(["Имя убийцы",item.getProp("k_name")]);
      _loc3_.push(["Уровень убийцы",item.getProp("k_lvl")]);
      _loc3_.push(["Имя жертвы",item.getProp("v_name")]);
      _loc3_.push(["Уровень жертвы",item.getProp("v_lvl")]);
      _loc3_.push(["Клан жертвы",item.getProp("v_clan")]);
      var _loc5_ = this.parseDate(item.getProp("time"));
      _loc3_.push(["Последнее убийство",_loc5_]);
      if(this.fullAnnotation)
      {
         this.addCost(_loc3_);
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.addItem(_loc3_[_loc2_][0],_loc3_[_loc2_][1]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function transport(item)
   {
      var _loc3_ = new Array();
      if(this.fullAnnotation)
      {
         this.addDesc(_loc3_);
      }
      var _loc4_ = (item.getProp("speed_mod") - 1) * 100;
      var _loc5_ = (1 - item.getProp("aggro_mod")) * 100;
      if(_loc4_ > 0)
      {
         _loc3_.push(["Скорость","+" + _loc4_ + " %"]);
      }
      else if(_loc4_ < 0)
      {
         _loc3_.push(["Скорость","-" + _loc4_ + " %"]);
      }
      if(_loc5_ > 0)
      {
         _loc3_.push(["Шанс перехвата","-" + _loc5_ + "%"]);
      }
      else if(_loc5_ < 0)
      {
         _loc3_.push(["Шанс перехвата","+" + _loc5_ + "%"]);
      }
      if(this.fullAnnotation)
      {
         this.addCost(_loc3_);
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.addItem(_loc3_[_loc2_][0],_loc3_[_loc2_][1]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function healItem(item)
   {
      var _loc3_ = new Array();
      if(this.fullAnnotation)
      {
         this.addDesc(_loc3_);
      }
      var _loc11_ = item.getProp("max_h_rest");
      var _loc12_ = item.getProp("max_st_rest");
      var _loc13_ = item.getProp("min_h_rest");
      var _loc14_ = item.getProp("min_st_rest");
      if(_loc11_ != 0)
      {
         _loc3_.push(["Восстанавливаемое здоровье",_loc13_ + "-" + _loc11_]);
      }
      if(_loc12_ != 0)
      {
         _loc3_.push(["Восстанавливаемое стамина",_loc14_ + "-" + _loc12_]);
      }
      var _loc5_ = item.getProp("need_attribs");
      str = this.readArray(_loc5_,this.attribsTitle);
      _loc3_.push(["Необходимые\rаттрибуты",str]);
      _loc5_ = item.getProp("need_skills");
      str = this.readArray(_loc5_,this.skillsTitle);
      _loc3_.push(["Необходимые\rнавыки",str]);
      _loc5_ = item.getProp("need_specs");
      str = this.readArray(_loc5_,this.specTitle);
      _loc3_.push(["Необходимые\rспециализации",str]);
      _loc3_.push(["Необходимый навык бойца",item.getProp("need_pvp_rep")]);
      var _loc10_ = item.getProp("str_bonus");
      var _loc9_ = item.getProp("dex_bonus");
      var _loc8_ = item.getProp("sta_bonus");
      var _loc7_ = item.getProp("per_bonus");
      var _loc6_ = item.getProp("int_bonus");
      var str = "- к силе " + _loc10_ + "\r- к ловкости " + _loc9_ + "\r- к телосложению " + _loc8_ + "\r- к восприятию " + _loc7_ + "\r- к интеллекту " + _loc6_;
      if(_loc10_ != 0 || _loc9_ != 0 || _loc8_ != 0 || _loc7_ != 0 || _loc6_ != 0)
      {
         _loc3_.push(["Плюсы",str]);
      }
      if(this.fullAnnotation)
      {
         this.addExchange(_loc3_);
         this.addSell(_loc3_);
         _loc3_.push(["Вес",item.getProp("_weight") + " г"]);
         this.addCost(_loc3_);
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.addItem(_loc3_[_loc2_][0],_loc3_[_loc2_][1]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function ammo(item)
   {
      var _loc3_ = new Array();
      if(this.fullAnnotation)
      {
         this.addDesc(_loc3_);
      }
      _loc3_.push(["Необходимый навык бойца",item.getProp("need_pvp_rep")]);
      var _loc10_ = !this.questRewardSize ? item.getProp("size") : this.questRewardSize;
      _loc3_.push(["Количество",_loc10_ + " шт"]);
      var _loc9_ = (item.getProp("range_mod") - 1) * 100;
      var _loc8_ = (1 - item.getProp("acc_mod")) * 100;
      var _loc7_ = (item.getProp("dam_mod") - 1) * 100;
      var _loc6_ = (item.getProp("st_mod") - 1) * 100;
      var _loc5_ = (item.getProp("piercing") - 1) * 100;
      if(_loc9_ != 0)
      {
         _loc3_.push(["Дальнобойность",(_loc9_ <= 0 ? "" : "+") + _loc9_ + "%"]);
      }
      if(_loc8_ != 0)
      {
         _loc3_.push(["Точность",(_loc8_ <= 0 ? "" : "+") + _loc8_ + "%"]);
      }
      if(_loc7_ != 0)
      {
         _loc3_.push(["Урон здоровью",(_loc7_ <= 0 ? "" : "+") + _loc7_ + "%"]);
      }
      if(_loc6_ != 0)
      {
         _loc3_.push(["Урон по выносливости",(_loc6_ <= 0 ? "" : "+") + _loc6_ + "%"]);
      }
      if(_loc5_ != 0)
      {
         _loc3_.push(["Бронебойность",(_loc5_ <= 0 ? "" : "+") + _loc5_ + "%"]);
      }
      if(this.fullAnnotation)
      {
         this.addExchange(_loc3_);
         this.addSell(_loc3_);
         _loc3_.push(["Вес 1 шт.",item.getProp("_weight") + " г"]);
         this.addCost(_loc3_);
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.addItem(_loc3_[_loc2_][0],_loc3_[_loc2_][1]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function breakString(item)
   {
      var _loc3_ = item.getProp("__break") != undefined ? item.getProp("__break") : "";
      var _loc4_ = item.getProp("max_break_cur") != undefined ? item.getProp("max_break_cur") : "";
      var _loc2_ = item.getProp("max_break_abs") != undefined ? item.getProp("max_break_abs") : "";
      if(_loc3_ == "")
      {
         return _loc2_;
      }
      return _loc3_ + " из " + _loc4_ + " (" + _loc2_ + ")";
   }
   function addCost(annotationArr)
   {
      var _loc4_ = this.item.getProp("cost");
      var _loc2_ = this.item.getProp("g_cost");
      var _loc3_ = this.item.getProp("bg_p_cost");
      if(_loc3_)
      {
         annotationArr.push(["Базовая цена: ",_loc3_ + " ПвП-баллов"]);
      }
      else if(_loc2_)
      {
         annotationArr.push(["Базовая цена: ",_loc2_ / 100 + " G"]);
      }
      else if(_loc4_)
      {
         annotationArr.push(["Базовая цена: ",_loc4_ + " Афро"]);
      }
   }
   function addExchange(annotationArr)
   {
      var _loc2_ = this.item.getProp("exchang");
      annotationArr.push(["Допустимость обмена",!_loc2_ ? "Нет" : "Да"]);
   }
   function addSell(annotationArr)
   {
      var _loc3_ = this.item.getProp("cost");
      var _loc2_ = this.item.getProp("exchang");
      annotationArr.push(["Допустимость продажи",!(_loc3_ && _loc2_) ? "Нет" : "Да"]);
   }
   function addDesc(annotationArr)
   {
      var _loc2_ = this.item.getProp("desc");
      if(_loc2_)
      {
         lol.utils.ParseString.replaceAll(_loc2_,"\"","\"");
         annotationArr.push([_loc2_ + "\r\r",""]);
      }
   }
   function parseDate(time_str)
   {
      var _loc9_ = Number(time_str.substring(0,4));
      var _loc7_ = Number(time_str.substring(5,7)) - 1;
      var _loc6_ = Number(time_str.substring(8,10));
      var _loc4_ = Number(time_str.substring(11,13));
      var _loc5_ = Number(time_str.substring(14,16));
      var _loc8_ = Number(time_str.substring(17,19));
      var _loc1_ = new Date();
      _loc1_.setFullYear(_loc9_);
      _loc1_.setMonth(_loc7_);
      _loc1_.setDate(_loc6_);
      _loc1_.setHours(_loc4_);
      _loc1_.setMinutes(_loc5_ - _loc1_.getTimezoneOffset());
      _loc1_.setSeconds(_loc8_);
      var _loc2_;
      switch(_loc1_.getMonth())
      {
         case 0:
            _loc2_ = "Янв.";
            break;
         case 1:
            _loc2_ = "Фев.";
            break;
         case 2:
            _loc2_ = "Мар.";
            break;
         case 3:
            _loc2_ = "Апр.";
            break;
         case 4:
            _loc2_ = "Мая";
            break;
         case 5:
            _loc2_ = "Июня";
            break;
         case 6:
            _loc2_ = "Июля";
            break;
         case 7:
            _loc2_ = "Авг.";
            break;
         case 8:
            _loc2_ = "Сент.";
            break;
         case 9:
            _loc2_ = "Окт.";
            break;
         case 10:
            _loc2_ = "Нояб.";
            break;
         case 11:
            _loc2_ = "Дек.";
      }
      _loc4_ = _loc1_.getHours() >= 10 ? _loc1_.getHours() : "0" + _loc1_.getHours();
      _loc5_ = _loc1_.getMinutes() >= 10 ? _loc1_.getMinutes() : "0" + _loc1_.getMinutes();
      return _loc1_.getDate() + " " + _loc2_ + " " + _loc1_.getFullYear() + "\r" + _loc4_ + ":" + _loc5_;
   }
   static function getTextDuration(milliseconds)
   {
      var _loc2_;
      var _loc1_ = Math.floor(milliseconds / 1000);
      var _loc5_;
      var _loc3_;
      var _loc6_;
      var _loc7_;
      var _loc4_;
      if(_loc1_ > 60)
      {
         _loc5_ = Math.floor(_loc1_ / 60);
         if(_loc1_ > 3600)
         {
            _loc3_ = Math.floor(_loc1_ / 3600);
            _loc6_ = Math.floor((_loc1_ - _loc3_ * 3600) / 60);
            _loc7_ = _loc1_ - _loc3_ * 3600 - _loc6_ * 60;
            if(_loc7_ != 0)
            {
               _loc4_ = _loc7_ + " с.";
            }
            else
            {
               _loc4_ = "0 с.";
            }
            _loc2_ = _loc3_ + " ч. " + _loc6_ + " м. " + _loc4_;
         }
         else
         {
            _loc7_ = _loc1_ - _loc5_ * 60;
            _loc2_ = _loc5_ + " м. " + _loc7_ + " c.";
         }
      }
      else
      {
         _loc2_ = _loc1_ + " c.";
      }
      return _loc2_;
   }
   function addItem(title, value)
   {
      var _loc4_ = this.name_txt.textHeight <= 10 ? 1 : 4;
      this.back.title._height = this.name_txt.textHeight + _loc4_ - 1;
      this.back.desc._y = Math.round(this.back.title._y + this.back.title._height + 1);
      this.desc_txt._y = Math.round(this.name_txt._y + this.name_txt.textHeight + 7);
      var _loc2_;
      var _loc3_;
      if(value != undefined)
      {
         _loc2_ = this.cont_mc.attachMovie("annotation_item","annotation_item",this.cont_mc.getNextHighestDepth());
         _loc3_ = this.cont_mc.attachMovie("annotation_line","annotation_line",this.cont_mc.getNextHighestDepth());
         _loc2_.title_txt.autoSize = true;
         _loc2_.value_txt.autoSize = true;
         _loc2_.title_txt.html = true;
         _loc2_.value_txt.html = true;
         _loc2_.title_txt.htmlText = title;
         _loc2_.value_txt.htmlText = value;
         this.arrItem.push(_loc2_);
         this.arrLine.push(_loc3_);
      }
   }
   function readArray(arr, titleArr)
   {
      var _loc5_ = "";
      var _loc1_ = 0;
      var _loc4_;
      while(_loc1_ < arr.length)
      {
         if(arr[_loc1_])
         {
            _loc4_ = !titleArr[_loc1_] ? "" : titleArr[_loc1_];
            _loc5_ += titleArr[_loc1_] + " " + arr[_loc1_] + "\r";
         }
         _loc1_ = _loc1_ + 1;
      }
      if(_loc5_ != "")
      {
         return _loc5_;
      }
   }
   function align()
   {
      this.cont_mc._y = Math.round(this.name_txt._y + this.name_txt._height + 5);
      var _loc3_ = 0;
      var _loc4_;
      var _loc2_ = 0;
      while(_loc2_ < this.arrItem.length)
      {
         if(this.arrItem[_loc2_].effect_icon != undefined)
         {
            this.arrItem[_loc2_].effect_icon._visible = true;
         }
         this.arrItem[_loc2_]._y = Math.round(_loc3_);
         _loc3_ = Math.round(this.arrItem[_loc2_]._y + this.arrItem[_loc2_]._height + 2);
         this.arrLine[_loc2_]._y = Math.round(_loc3_ - 2);
         this.arrLine[_loc2_]._x = 1;
         if(_loc2_ == this.arrItem.length - 1)
         {
            this.arrLine[_loc2_].removeMovieClip();
            _loc4_ = _loc3_;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.back_bottom._y = Math.round(_loc4_ + this.cont_mc._y + 5);
      this.back_middle._height = this.back_bottom._y - this.back_middle._y;
      this.cont_mc._visible = true;
   }
}
