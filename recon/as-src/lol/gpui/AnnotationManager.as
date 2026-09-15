class lol.gpui.AnnotationManager
{
   static var PAUSE_TIMER;
   static var X;
   static var Y;
   static var _item;
   static var _lX;
   static var _rX;
   static var _tY;
   static var annotation;
   static var annotationSec;
   static var cont_mc;
   static var ANNOTATION_WIDTH = 210;
   function AnnotationManager()
   {
   }
   static function create(item, lX, rX, tY)
   {
      lol.gpui.AnnotationManager.PAUSE_TIMER.Clear();
      lol.gpui.AnnotationManager.clear();
      var _loc2_;
      var _loc4_;
      var _loc3_;
      if(item.inited)
      {
         lol.gpui.AnnotationManager.cont_mc = lol.core.SceneShifter.linkWindow;
         lol.gpui.AnnotationManager.annotation.removeMovieClip();
         lol.gpui.AnnotationManager.annotationSec.removeMovieClip();
         lol.gpui.AnnotationManager.annotation = lol.gpui.Annotation(lol.gpui.AnnotationManager.cont_mc.attachMovie("setAnnotation","annotation",lol.gpui.AnnotationManager.cont_mc.getNextHighestDepth()));
         lol.gpui.AnnotationManager.X = lol.gpui.AnnotationManager.cont_mc._xmouse;
         lol.gpui.AnnotationManager.Y = lol.gpui.AnnotationManager.cont_mc._ymouse;
         lol.gpui.AnnotationManager.annotation._x = lol.gpui.AnnotationManager.X + rX;
         lol.gpui.AnnotationManager.annotation._y = lol.gpui.AnnotationManager.Y - tY;
         lol.gpui.AnnotationManager.annotation._visible = false;
         if(Key.isDown(17))
         {
            lol.gpui.AnnotationManager.annotation.showInfo(item,true);
         }
         else if(Key.isDown(16))
         {
            lol.gpui.AnnotationManager.annotation.showInfo(item,true);
            lol.gpui.AnnotationManager.annotation.myFlag = true;
            if(lol.gpui.AnnotationManager.getMyItem(item))
            {
               lol.gpui.AnnotationManager.createSec(lol.gpui.AnnotationManager.getMyItem(item),true,true);
            }
         }
         else
         {
            lol.gpui.AnnotationManager.annotation.showInfo(item);
         }
         _loc2_ = item.getProp("processed_effects");
         _loc4_ = item.getProp("effects_prob");
         if(_loc2_ && _loc4_ && !Key.isDown(16))
         {
            if(_loc2_.length > 0 && _loc2_.length == _loc4_.length)
            {
               lol.gpui.AnnotationManager.createEffectsTooltip(_loc2_,_loc4_,true);
            }
         }
         _loc3_ = item.getProp("setTypeID");
         if(_loc3_ && !Key.isDown(16))
         {
            if(lol.core.sets.SetManager.getSet(_loc3_).inited)
            {
               lol.gpui.AnnotationManager.createSec(lol.core.sets.SetManager.getSet(_loc3_),true);
            }
            else
            {
               lol.core.sets.SetManager.getSet(_loc3_).addEventListener(lol.core.sets.SetObject.UPDATE_SET,lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.setUpdate);
            }
         }
         lol.gpui.AnnotationManager.PAUSE_TIMER = new lol.utils.Timeout(lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.align,100,lX,rX,tY);
      }
      else
      {
         lol.gpui.AnnotationManager._lX = lX;
         lol.gpui.AnnotationManager._rX = rX;
         lol.gpui.AnnotationManager._tY = tY;
         lol.gpui.AnnotationManager._item = item;
         item.addEventListener("itemUpdate",lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.itemUpdate);
      }
   }
   static function createOneEffectAnnotation(effect, lX, rX, tY)
   {
      lol.gpui.AnnotationManager.PAUSE_TIMER.Clear();
      lol.gpui.AnnotationManager.clear();
      lol.gpui.AnnotationManager.cont_mc = lol.core.SceneShifter.linkWindow;
      lol.gpui.AnnotationManager.annotation.removeMovieClip();
      lol.gpui.AnnotationManager.annotationSec.removeMovieClip();
      lol.gpui.AnnotationManager.annotation = lol.gpui.Annotation(lol.gpui.AnnotationManager.cont_mc.attachMovie("setAnnotation","annotation",lol.gpui.AnnotationManager.cont_mc.getNextHighestDepth()));
      lol.gpui.AnnotationManager.X = lol.gpui.AnnotationManager.cont_mc._xmouse;
      lol.gpui.AnnotationManager.Y = lol.gpui.AnnotationManager.cont_mc._ymouse;
      lol.gpui.AnnotationManager.annotation._x = lol.gpui.AnnotationManager.X + rX;
      lol.gpui.AnnotationManager.annotation._y = lol.gpui.AnnotationManager.Y - tY;
      lol.gpui.AnnotationManager.annotation._visible = false;
      lol.gpui.AnnotationManager.annotation.showInfo(effect,true);
      lol.gpui.AnnotationManager.PAUSE_TIMER = new lol.utils.Timeout(lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.align,100,lX,rX,tY);
   }
   static function createEffectsTooltip(effects, effects_prob, full, my)
   {
      lol.gpui.AnnotationManager.PAUSE_TIMER.Clear();
      lol.gpui.AnnotationManager.annotationSec.removeMovieClip();
      lol.gpui.AnnotationManager.annotationSec = lol.gpui.Annotation(lol.gpui.AnnotationManager.cont_mc.attachMovie("setAnnotation","setAnnotation",lol.gpui.AnnotationManager.cont_mc.getNextHighestDepth()));
      lol.gpui.AnnotationManager.annotationSec.showEffectsInfo(effects,effects_prob,full,my);
      lol.gpui.AnnotationManager.annotationSec._x = lol.gpui.AnnotationManager.annotation._x + lol.gpui.AnnotationManager.ANNOTATION_WIDTH;
      lol.gpui.AnnotationManager.annotationSec._y = lol.gpui.AnnotationManager.annotation._y;
      lol.gpui.AnnotationManager.annotationSec._visible = false;
      lol.gpui.AnnotationManager.PAUSE_TIMER = new lol.utils.Timeout(lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.align,100);
   }
   static function createSec(item, full, my)
   {
      lol.gpui.AnnotationManager.PAUSE_TIMER.Clear();
      lol.gpui.AnnotationManager.annotationSec.removeMovieClip();
      lol.gpui.AnnotationManager.annotationSec = lol.gpui.Annotation(lol.gpui.AnnotationManager.cont_mc.attachMovie("setAnnotation","setAnnotation",lol.gpui.AnnotationManager.cont_mc.getNextHighestDepth()));
      lol.gpui.AnnotationManager.annotationSec.showInfo(item,full,my);
      lol.gpui.AnnotationManager.annotationSec._x = lol.gpui.AnnotationManager.annotation._x + lol.gpui.AnnotationManager.ANNOTATION_WIDTH;
      lol.gpui.AnnotationManager.annotationSec._y = lol.gpui.AnnotationManager.annotation._y;
      lol.gpui.AnnotationManager.annotationSec._visible = false;
      lol.gpui.AnnotationManager.PAUSE_TIMER = new lol.utils.Timeout(lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.align,100);
   }
   static function getMyItem(item)
   {
      var _loc2_;
      var _loc3_;
      if(item.rootID == lol.core.objects.Item.WEAR)
      {
         _loc2_ = item.getProp("slot_type");
         _loc3_ = lol.core.objects.Wear(lol.core.player.Slot(lol.core.Master.getInstance().gamer.equipment.slots_arr[_loc2_]).item);
         return _loc3_;
      }
      if(item.rootID == lol.core.objects.Item.FIRE_ARM || item.rootID == lol.core.objects.Item.COLD_ARM)
      {
         _loc3_ = lol.core.Master.getInstance().gamer.equipment.primaryItem;
         if(_loc3_.rootID != lol.core.objects.Item.FIST)
         {
            return lol.core.Master.getInstance().gamer.equipment.primaryItem;
         }
      }
   }
   static function itemUpdate(obj)
   {
      obj.target.removeEventListener("itemUpdate",lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.create);
      lol.gpui.AnnotationManager.create(lol.gpui.AnnotationManager._item,lol.gpui.AnnotationManager._lX,lol.gpui.AnnotationManager._rX,lol.gpui.AnnotationManager._tY);
   }
   static function setUpdate(obj)
   {
      obj.target.removeEventListener(lol.core.sets.SetObject.UPDATE_SET,lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.setUpdate);
      lol.gpui.AnnotationManager.create(lol.gpui.AnnotationManager._item,lol.gpui.AnnotationManager._lX,lol.gpui.AnnotationManager._rX,lol.gpui.AnnotationManager._tY);
   }
   static function align(lX, rX, tY)
   {
      var _loc2_;
      var _loc1_;
      if(!lol.gpui.AnnotationManager.annotationSec)
      {
         _loc2_ = lol.gpui.AnnotationManager.annotation._x + lol.gpui.AnnotationManager.ANNOTATION_WIDTH + Stage.width / 2;
         _loc1_ = lol.gpui.AnnotationManager.annotation._y + lol.gpui.AnnotationManager.annotation._height + Stage.height / 2;
      }
      else
      {
         _loc2_ = lol.gpui.AnnotationManager.annotation._x + lol.gpui.AnnotationManager.ANNOTATION_WIDTH + lol.gpui.AnnotationManager.ANNOTATION_WIDTH + Stage.width / 2;
         if(lol.gpui.AnnotationManager.annotation._height > lol.gpui.AnnotationManager.annotationSec._height)
         {
            _loc1_ = lol.gpui.AnnotationManager.annotation._y + lol.gpui.AnnotationManager.annotation._height + Stage.height / 2;
         }
         else
         {
            _loc1_ = lol.gpui.AnnotationManager.annotationSec._y + lol.gpui.AnnotationManager.annotationSec._height + Stage.height / 2;
         }
      }
      if(Stage.width < _loc2_)
      {
         lol.gpui.AnnotationManager.annotation._x = lol.gpui.AnnotationManager.X - lX - lol.gpui.AnnotationManager.ANNOTATION_WIDTH;
         if(lol.gpui.AnnotationManager.annotationSec)
         {
            lol.gpui.AnnotationManager.annotation._x -= lol.gpui.AnnotationManager.ANNOTATION_WIDTH;
            lol.gpui.AnnotationManager.annotationSec._x = lol.gpui.AnnotationManager.annotation._x + lol.gpui.AnnotationManager.ANNOTATION_WIDTH;
         }
      }
      if(Stage.height < _loc1_)
      {
         if(!lol.gpui.AnnotationManager.annotationSec)
         {
            lol.gpui.AnnotationManager.annotation._y = Stage.height / 2 - lol.gpui.AnnotationManager.annotation._height;
         }
         else if(lol.gpui.AnnotationManager.annotation._height > lol.gpui.AnnotationManager.annotationSec._height)
         {
            lol.gpui.AnnotationManager.annotation._y = Stage.height / 2 - lol.gpui.AnnotationManager.annotation._height;
            lol.gpui.AnnotationManager.annotationSec._y = lol.gpui.AnnotationManager.annotation._y;
         }
         else
         {
            lol.gpui.AnnotationManager.annotationSec._y = Stage.height / 2 - lol.gpui.AnnotationManager.annotationSec._height;
            lol.gpui.AnnotationManager.annotation._y = lol.gpui.AnnotationManager.annotationSec._y;
         }
      }
      lol.gpui.AnnotationManager.annotation._visible = true;
      lol.gpui.AnnotationManager.annotationSec._visible = true;
   }
   static function clear()
   {
      lol.gpui.AnnotationManager.annotation.kill();
      lol.gpui.AnnotationManager.annotationSec.kill();
      lol.gpui.AnnotationManager._item.removeEventListener("itemUpdate",lol.gpui.AnnotationManager,lol.gpui.AnnotationManager.itemUpdate);
      lol.gpui.AnnotationManager.annotation.removeMovieClip();
      lol.gpui.AnnotationManager.annotationSec.removeMovieClip();
      lol.gpui.AnnotationManager.annotationSec = null;
   }
}
